#!/usr/bin/env python3

# lektrix
# Copyright (C) 2024  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

"""Common functions for use with the KAMSTRUP electricity meter"""

import datetime as dt
import logging
import re
import sys
import traceback

import constants
import numpy as np
import pandas as pd
import serial  # type: ignore[import-not-found]  # (cannot be imported in dev environment)

LOGGER: logging.Logger = logging.getLogger(__name__)


class Kamstrup:  # pylint: disable=too-many-instance-attributes
    """Class to interact with the P1-port."""

    def __init__(self, debug: bool = False) -> None:  # pylint: disable=too-many-instance-attributes
        self.PORT = serial.Serial()
        self.PORT.baudrate = 9600
        self.PORT.bytesize = serial.SEVENBITS
        self.PORT.parity = serial.PARITY_EVEN
        self.PORT.stopbits = serial.STOPBITS_ONE
        self.PORT.xonxoff = True
        self.PORT.rtscts = False
        self.PORT.dsrdtr = False
        self.PORT.timeout = 15
        self.PORT.port = "/dev/ttyUSB0"

        self.PORT.open()
        serial.XON  # noqa  # pylint: disable=W0104

        self.dt_format = constants.DT_FORMAT  # "%Y-%m-%d %H:%M:%S"
        # starting values
        self.electra1in = np.nan
        self.electra2in = np.nan
        self.electra1out = np.nan
        self.electra2out = np.nan
        self.powerin = np.nan
        self.powerout = np.nan
        self.tarif = 1
        self.swits = 0
        self.list_data: list = []

        self.debug: bool = debug
        if debug:
            if len(LOGGER.handlers) == 0:
                LOGGER.addHandler(logging.StreamHandler(sys.stdout))
            LOGGER.level = logging.DEBUG
            LOGGER.debug("Debugging on.")
            self.telegram: list = []

    def get_telegram(self) -> bool:
        """Fetch a telegram from the serialport.

        Returns:
            (bool): valid telegram received True or False
        """
        receiving = True
        valid_telegram = False
        # countdown counter used to prevent infinite loops
        loops2go = 40
        # storage space for the telegram
        telegram = []
        # end of line delimiter
        # delim = "\x0a"
        # line = ""
        while receiving:
            try:
                line = str(self.PORT.readline().strip(), "utf-8")
                if line == "!":
                    # detect end of telegram
                    receiving = False
                    # validate correct end of telegram
                    valid_telegram = True
                if line != "":
                    # remember meaningful content
                    telegram.append(line)
            except serial.SerialException:
                LOGGER.critical("*** Serialport read error:")
                LOGGER.error(traceback.format_exc())
                valid_telegram = False
                receiving = False
            except UnicodeDecodeError:
                LOGGER.critical("*** Unicode Decode error:")
                LOGGER.error(traceback.format_exc())
                valid_telegram = False
                receiving = False

            loops2go = loops2go - 1
            if loops2go < 0:
                receiving = False

        # validate correct start of telegram
        if telegram[0][0] != "/":
            valid_telegram = False

        # store final result
        # fmt: off
        if valid_telegram:
            if self.debug:
                self.telegram = telegram
                with open("/tmp/kamstrup.raw", "w", encoding="utf-8") as output_file:  # nosec B108
                    for line in self.telegram:
                        output_file.write(f"{line}\n")
            self.list_data.append(self._translate_telegram(telegram))
        # fmt: on
        return valid_telegram

    def _translate_telegram(self, telegram: list) -> dict:
        """Translate the telegram to a dict.

        kW or kWh are converted to W resp. kW

        Returns:
            (dict): data converted to a dict.
        """
        LOGGER.debug(f"    {telegram}")
        for element in telegram:
            try:
                line: list[str] = re.split(r"[\(\*\)]", element)
                # ['1-0:1.8.1', '00175.402', 'kWh', '']  T1 in
                if line[0] == "1-0:1.8.1":
                    self.electra1in = int(float(line[1]) * 1000)
                # ['1-0:1.8.2', '00136.043', 'kWh', '']  T2 in
                if line[0] == "1-0:1.8.2":
                    self.electra2in = int(float(line[1]) * 1000)
                # ['1-0:2.8.1', '00000.000', 'kWh', '']  T1 out
                if line[0] == "1-0:2.8.1":
                    self.electra1out = int(float(line[1]) * 1000)
                # ['1-0:2.8.2', '00000.000', 'kWh', '']  T2 out
                if line[0] == "1-0:2.8.2":
                    self.electra2out = int(float(line[1]) * 1000)
                # ['0-0:96.14.0', '0002', '']  tarif 1 or 2
                if line[0] == "0-0:96.14.0":
                    self.tarif = int(line[1])
                # ['1-0:1.7.0', '0000.32', 'kW', '']  power in
                if line[0] == "1-0:1.7.0":
                    self.powerin = int(float(line[1]) * 1000)
                # ['1-0:2.7.0', '0000.00', 'kW', ''] power out
                if line[0] == "1-0:2.7.0":
                    self.powerout = int(float(line[1]) * 1000)
                # ['0-0:17.0.0', '999', 'A', ''] threshold electricity;
                # not recorded
                # ['0-0:96.3.10', '1', '']  powerusage (1)
                #                           or powermanufacturing ()
                if line[0] == "0-0:96.3.10":
                    self.swits = int(line[1])
                    # swits is not always present. The value will
                    # change *if* present in the telegram.
                # ['0-0:96.13.1', '', ''] text message code
                # not recorded
                # ['0-0:96.13.0', '', ''] text message
                # not recorded
            except ValueError:
                LOGGER.critical("*** Conversion not possible for element:")
                LOGGER.error(f"    {element}")
                LOGGER.error("*** Extracted from telegram:")
                LOGGER.error(f"    {telegram}")
        idx_dt: dt.datetime = dt.datetime.now()
        epoch = int(idx_dt.timestamp())

        return {
            "sample_time": idx_dt.strftime(self.dt_format),
            "sample_epoch": epoch,
            "T1in": self.electra1in,
            "T2in": self.electra2in,
            "powerin": self.powerin,
            "T1out": self.electra1out,
            "T2out": self.electra2out,
            "powerout": self.powerout,
            "tarif": self.tarif,
            "swits": self.swits,
        }

    def compact_data(self, data) -> tuple:
        """
        Compact the ten-second data into 15-minute data

        Args:
            data (list): list of dicts containing 10-second data from the electricity meter

        Returns:
            (list): list of dicts containing compacted 15-minute data
        """

        def _convert_time_to_epoch(date_to_convert) -> int:
            return int(pd.Timestamp(date_to_convert).timestamp())

        def _convert_time_to_text(date_to_convert) -> str:
            return str(pd.Timestamp(date_to_convert).strftime(constants.DT_FORMAT))

        df = pd.DataFrame(data)
        df = df.set_index("sample_time")
        df.index = pd.to_datetime(df.index, format=constants.DT_FORMAT, utc=False)
        # resample to monotonic timeline
        df_out = df.resample("15min", label="right").max()
        # df_mean = df.resample("15min", label="right").mean()

        df_out["powerin"] = df_out["powerin"].astype(int)
        df_out["powerout"] = df_out["powerout"].astype(int)
        # recreate column 'sample_time' that was lost to the index
        df_out["sample_time"] = df_out.index.to_frame(name="sample_time")
        df_out["sample_time"] = df_out["sample_time"].apply(_convert_time_to_text)

        # recalculate 'sample_epoch'
        df_out["sample_epoch"] = df_out["sample_time"].apply(_convert_time_to_epoch)
        result_data = df_out.to_dict("records")  # list of dicts

        df = df[df["sample_epoch"] > np.max(df_out["sample_epoch"])]  # pylint: disable=E1136
        remain_data = df.to_dict("records")
        LOGGER.debug(f"Result: {result_data}")
        LOGGER.debug(f"Remain: {remain_data}\n")
        return result_data, remain_data
