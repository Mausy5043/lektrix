#!/usr/bin/env python3

# lektrix
# Copyright (C) 2024  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

# https://api-documentation.homewizard.com/docs/category/api-v1

"""Common functions for use with the Home Wizard P1 electricity meter dongle using the API/v1"""

# import asyncio
import datetime as dt
import logging
import sys
import time

import constants
import numpy as np
import pandas as pd
from homewizard_energy import HomeWizardEnergyV1
from libzeroconf import discover as zcd

LOGGER: logging.Logger = logging.getLogger(__name__)


# https://api-documentation.homewizard.com/docs/category/api-v1


class WizP1_v1:  # pylint: disable=too-many-instance-attributes
    """Class to interact with the Home Wizard P1-dongle."""

    def __init__(self, debug: bool = False) -> None:  # pylint: disable=too-many-instance-attributes
        # get a HomeWizard IP
        self.ip = ""
        deltat: float = 10.0
        while not self.ip and deltat < 300:
            _howip = zcd.get_ip(service="_hwenergy", filtr="HWE-P1")
            if _howip:
                self.ip = _howip[0]
            else:
                LOGGER.error(f"No HomeWizard P1 found. Retrying in {deltat} seconds.")
                time.sleep(deltat)
                deltat = int(deltat * 14.142) / 10

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
        self.firstcall = True
        if debug:
            if len(LOGGER.handlers) == 0:
                LOGGER.addHandler(logging.StreamHandler(sys.stdout))
            LOGGER.level = logging.DEBUG
            LOGGER.debug("Debugging on.")
            self.telegram: list = []

    async def get_telegram(self):
        """Fetch a telegram from the serialport.

        Returns:
            (bool): valid telegram received True or False
        """
        async with HomeWizardEnergyV1(host=self.ip) as _api:
            if self.debug and self.firstcall:
                # Get device information, like firmware version
                wiz_dev = await _api.device()
                LOGGER.debug(wiz_dev)
                LOGGER.debug("")
                self.firstcall = False

            # Get measurements
            wiz_data = await _api.data()
            LOGGER.debug(wiz_data)
            LOGGER.debug("---")

        self.list_data.append(self._translate_telegram(wiz_data))
        LOGGER.debug(self.list_data)
        LOGGER.debug("*-*")

    def _translate_telegram(self, telegram) -> dict:
        """Translate the telegram to a dict.

        kW or kWh are converted to W resp. kW

        Returns:
            (dict): data converted to a dict.
        """
        self.electra1in = int(telegram.energy_import_t1_kwh * 1000)
        self.electra2in = int(telegram.energy_import_t2_kwh * 1000)
        self.electra1out = int(telegram.energy_export_t1_kwh * 1000)
        self.electra2out = int(telegram.energy_export_t2_kwh * 1000)
        self.tarif = telegram.tariff
        self.powerin = telegram.power_w
        self.powerout = 0.0
        self.swits = 1
        if self.powerin < 0.0:
            self.swits = 0
            self.powerout = self.powerin
            self.powerin = 0.0

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
