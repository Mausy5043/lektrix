#!/usr/bin/env python3

# lektrix
# Copyright (C) 2025  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Common functions for use with the Sessy home battery."""

import datetime as dt
import json
import logging
import sys

import constants as cs
import numpy as np
import pandas as pd
from mausy5043_common import funsessy as fses

LOGGER: logging.Logger = logging.getLogger(__name__)


class SesBat:
    """Class to interact with the Sessy battery."""

    def __init__(self, debug: bool = False) -> None:
        self.debug: bool = debug
        self.dt_format = cs.DT_FORMAT
        # starting values
        self.soc = 0
        self.soh = 0
        self.list_data: list = []

        # set-up logging
        if debug:
            if len(LOGGER.handlers) == 0:
                LOGGER.addHandler(logging.StreamHandler(sys.stdout))
            LOGGER.setLevel(logging.DEBUG)
            LOGGER.debug("Debugging on.")
            self.telegram: list = []

        # process config file
        try:
            with open(cs.BATTERY["config"], encoding="utf-8") as _json_file:
                _cfg = json.load(_json_file)
        except FileNotFoundError:
            LOGGER.error("Config file not found.")
            sys.exit(1)
        except json.JSONDecodeError:
            LOGGER.error("Error decoding JSON config file.")
            sys.exit(1)
        try:
            self.b1_ip: str = _cfg["bat1"]["ip"]
            self.b1_usr: str = _cfg["bat1"]["username"]
            self.b1_pwd: str = _cfg["bat1"]["password"]
            self.b2_ip: str = _cfg["bat2"]["ip"]
            self.b2_usr: str = _cfg["bat2"]["username"]
            self.b2_pwd: str = _cfg["bat2"]["password"]
        except KeyError as her:
            LOGGER.error(f"KeyError: {her}")
            LOGGER.error("Please check the config file.")
            sys.exit(1)

        # connect to the Sessy devices
        self.bat1 = fses.MySessyBattery(
            ip=self.b1_ip, user=self.b1_usr, token=self.b1_pwd, debug=self.debug
        )
        self.bat2 = fses.MySessyBattery(
            ip=self.b2_ip, user=self.b2_usr, token=self.b2_pwd, debug=self.debug
        )

        self.bat1.connect()
        self.bat2.connect()

    def get_telegram(self):
        """Fetch data from the devices.

        Returns:
            Nothing
        """
        _b1_data = self.bat1.get_measurement()
        _b2_data = self.bat2.get_measurement()

        self.list_data.append(self._translate_telegram([_b1_data, _b2_data]))
        LOGGER.debug(f"\n\n{self.list_data}")
        LOGGER.debug("*-*")

    def _translate_telegram(self, telegram: list) -> dict:
        """Translate the telegram to a dict.

        SoC and SoH are in fractions and converted to centipercent.

        Returns:
            (dict): data extracted and converted to a dict.
        """
        # fmt: off
        _b1 = telegram[0]
        LOGGER.debug(f"Battery #1:\n{json.dumps(_b1, indent=1)}")
        _b2 = telegram[1]
        LOGGER.debug(f"Battery #2:\n{json.dumps(_b2, indent=1)}")
        # State of Charge and State of Health are in centipercent
        _soc1 = _b1["sessy"]["state_of_charge"] * 10000
        _soh1 = 1000  # _b1["soh"] * 1000
        _soc2 = _b2["sessy"]["state_of_charge"] * 10000
        _soh2 = 1000  # _b1["soh"] * 1000
        self.soc = int((_soc1 + _soc2) / 2)
        self.soh = int((_soh1 + _soh2) / 2)

        idx_dt: dt.datetime = dt.datetime.now()
        epoch = int(idx_dt.timestamp())

        return {
            "sample_time": idx_dt.strftime(self.dt_format),
            "sample_epoch": epoch,
            "site_id": cs.BATTERY["template"]["site_id"],
            "soc": self.soc,  # State of Charge of the battery
            "soh": self.soh,  # State of Health of the battery
        }
        # fmt: on

    @staticmethod
    def compact_data(data: list[dict]) -> tuple:
        """Compact the data into N-minute data (N = report_interval).

        Args:
            data (list): list of dicts containing data from the electricity meter

        Returns:
            (list): list of dicts containing compacted N-minute data
        """

        def _convert_time_to_epoch(date_to_convert) -> int:
            return int(pd.Timestamp(date_to_convert).timestamp())

        def _convert_time_to_text(date_to_convert) -> str:
            return str(pd.Timestamp(date_to_convert).strftime(cs.DT_FORMAT))

        df = pd.DataFrame(data)
        LOGGER.debug(f"Original dataframe:\n{df.to_markdown(floatfmt='.3f')}")
        # for correct cost calculation sample_time must be in the correct hour.
        # sample_time reflects the time of the start of the next sample, but it
        # should reflect the end of its period.
        # so we will steal 5 seconds from "sample_time" to make it look like it
        # was taken at the end of the period.
        df["sample_time"] = pd.to_datetime(
            df["sample_time"], format=cs.DT_FORMAT, utc=False
        ) - pd.Timedelta(seconds=5)
        LOGGER.debug(f"Timeshifted dataframe:\n{df.to_markdown(floatfmt='.3f')}")
        # drop the temporary columns
        # df.drop(labels=["st_0", "st-5"], axis=1, inplace=True, errors="ignore")
        df = df.set_index("sample_time")
        df.index = pd.to_datetime(df.index, format=cs.DT_FORMAT, utc=False)

        # resample to monotonic timeline, use label=left to get the correct timeperiod
        resample_time = f"{cs.BATTERY["report_interval"] / 60}min"
        df_out = df.resample(resample_time, label="left").max()
        df_mean = df.resample(resample_time, label="left").mean()
        LOGGER.debug(f"Resampled (max) dataframe:\n{df_out.to_markdown(floatfmt='.3f')}")
        # reset 'site_id'
        df_out["site_id"] = cs.BATTERY["template"]["site_id"]
        df_out["soc"] = df_mean["soc"]
        df_out["soh"] = df_mean["soh"]
        LOGGER.debug(f"Added means to dataframe:\n{df_out.to_markdown(floatfmt='.3f')}")

        # recreate column 'sample_time' that was lost to the index
        df_out["sample_time"] = df_out.index.to_frame(name="sample_time")
        LOGGER.debug(
            f"recreated column 'sample_time' dataframe:\n{df_out.to_markdown(floatfmt='.3f')}"
        )
        df_out["sample_time"] = df_out["sample_time"].apply(_convert_time_to_text)

        # recalculate 'sample_epoch' from the new 'sample_time'
        df_out["sample_epoch"] = df_out["sample_time"].apply(_convert_time_to_epoch)
        result_data: list[dict] = df_out.to_dict("records")
        # ignore samples that seem to be in the future
        df = df[df["sample_epoch"] > np.max(df_out["sample_epoch"])]
        remain_data: list[dict] = df.to_dict("records")

        LOGGER.debug(f"Result: {json.dumps(result_data, indent=2)}\n")
        LOGGER.debug(f"Remain: {json.dumps(remain_data, indent=2)}\n")
        return result_data, remain_data
