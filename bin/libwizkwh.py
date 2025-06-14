#!/usr/bin/env python3

# lektrix
# Copyright (C) 2025  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Common functions for use with the Home Wizard kWh-meter"""

import datetime as dt
import json
import logging
import sys

import constants as cs
import numpy as np
import pandas as pd
from mausy5043_common import funhomewizard as hwz

LOGGER: logging.Logger = logging.getLogger(__name__)


class WizkWh:
    """Class to interact with the Home Wizard kWh-meter."""

    def __init__(self, debug: bool = False) -> None:
        self.debug: bool = debug
        self.dt_format = cs.DT_FORMAT
        # starting values
        self.ev_elec_in = np.nan
        self.pv_elec_in = np.nan
        self.ev_elec_out = np.nan
        self.pv_elec_out = np.nan
        self.ev_voltage = np.nan
        self.pv_voltage = np.nan
        self.ev_freq = np.nan
        self.pv_freq = np.nan
        self.ev_pf = np.nan
        self.pv_pf = np.nan
        self.home_freq = np.nan
        self.home_voltage = np.nan
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
            with open(cs.WIZ_KWH["config"], encoding="utf-8") as _json_file:
                _cfg = json.load(_json_file)
        except FileNotFoundError:
            LOGGER.error("Config file not found.")
            sys.exit(1)
        except json.JSONDecodeError:
            LOGGER.error("Error decoding JSON config file.")
            sys.exit(1)
        try:
            self.ev_serial: str = _cfg["EV"]["serial"]
            self.ev_token: str = _cfg["EV"]["token"]
            self.pv_serial: str = _cfg["PV"]["serial"]
            self.pv_token: str = _cfg["PV"]["token"]
            self.p1_serial: str = _cfg["P1"]["serial"]
            self.p1_token: str = _cfg["P1"]["token"]
        except KeyError as her:
            LOGGER.error(f"KeyError: {her}")
            LOGGER.error("Please check the config file.")
            sys.exit(1)

        # NB: mausy5043_common displays device info.
        # connect to the Home Wizard devices
        try:
            self.ev_hwe = hwz.MyHomeWizard(
                serial=self.ev_serial, token=self.ev_token, debug=self.debug
            )
        except Exception as err:
            LOGGER.error(f"Error connecting to EV device: {err}")
        try:
            self.pv_hwe = hwz.MyHomeWizard(
                serial=self.pv_serial, token=self.pv_token, debug=self.debug
            )
        except Exception as err:
            LOGGER.error(f"Error connecting to PV device: {err}")
        try:
            self.p1_hwe = hwz.MyHomeWizard(
                serial=self.p1_serial, token=self.p1_token, debug=self.debug
            )
        except Exception as err:
            LOGGER.error(f"Error connecting to P1 device: {err}")
        self.ev_hwe.connect()
        self.pv_hwe.connect()
        self.p1_hwe.connect()

    def get_telegram(self):
        """Fetch data from the devices.

        Returns:
            Nothing
        """
        _ev_data = None
        _pv_data = None
        _p1_data = None
        try:
            _ev_data = self.ev_hwe.get_measurement()
        except Exception as err:
            LOGGER.error(f"Error getting data from EV device: {err}")
        try:
            _pv_data = self.pv_hwe.get_measurement()
        except Exception as err:
            LOGGER.error(f"Error getting data from EV device: {err}")
        try:
            _p1_data = self.p1_hwe.get_measurement()
        except Exception as err:
            LOGGER.error(f"Error getting data from EV device: {err}")

        self.list_data.append(self._translate_telegram([_ev_data, _pv_data, _p1_data]))
        LOGGER.debug(f"\n\n{self.list_data}")
        LOGGER.debug("*-*")

    def _translate_telegram(self, telegram: list) -> dict:
        """Translate the telegram to a dict.

        kW or kWh are converted to W resp. kW

        Returns:
            (dict): data converted to a dict.
        """
        # fmt: off
        _ev = telegram[0]
        LOGGER.debug(f"EV:\n{_ev}")
        _pv = telegram[1]
        LOGGER.debug(f"PV:\n{_pv}")
        _p1 = telegram[2]
        LOGGER.debug(f"P1:\n{_p1}")
        if _ev:
            self.ev_elec_in = int(_ev.energy_export_kwh * 1000)  # EV kWH-meter is connected wrong way round
            self.ev_elec_out = int(_ev.energy_import_kwh * -1000)  # EV kWH-meter is connected wrong way round
            self.ev_voltage = _ev.voltage_v
            self.ev_freq = _ev.frequency_hz
        if _pv:
            self.pv_elec_in = int(_pv.energy_export_kwh * 1000)  # PV kWH-meter is connected wrong way round
            self.pv_elec_out = int(_pv.energy_import_kwh * -1000)  # PV kWH-meter is connected wrong way round
            self.pv_voltage = _pv.voltage_v
            self.pv_freq = _pv.frequency_hz
        if _p1:
            self.p1_elec_in = int(_p1.energy_import_kwh * 1000)
            self.p1_elec_out = int(_p1.energy_export_kwh * -1000)
            # not available on P1-dongle w/ KAMSTRUP
            # self.p1_voltage = int(_p1.voltage_v * 10)
            # not available on P1-dongle w/ KAMSTRUP
            # self.p1_freq = int(_p1.active_frequency_hz * 10)
        self.home_voltage = int(np.nanmean([self.ev_voltage, self.pv_voltage]) * 10)
        self.home_freq = int(np.nanmean([self.ev_freq, self.pv_freq]) * 10)

        idx_dt: dt.datetime = dt.datetime.now()
        epoch = int(idx_dt.timestamp())

        return {
            "sample_time": idx_dt.strftime(self.dt_format),
            "sample_epoch": epoch,
            "site_id": cs.WIZ_KWH["template"]["site_id"],
            "exp": self.p1_elec_out,  # exported to grid
            "imp": self.p1_elec_in,  # imported from grid to home
            "gen": self.pv_elec_out,  # consumed by PV (feeding to battery)
            "gep": self.pv_elec_in,  # generated & delivered by PV to home (solar production or from battery)
            "evn": self.ev_elec_out,  # consumed by EV
            "evp": self.ev_elec_in,  # V2H from EV to home
            "v1": self.home_voltage,  # avg voltage in the home
            "frq": self.home_freq,  # avg frequency in the home
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
        resample_time = f"{cs.WIZ_KWH["report_interval"] / 60}min"
        df_out = df.resample(resample_time, label="left").max()
        df_mean = df.resample(resample_time, label="left").mean()
        LOGGER.debug(f"Resampled (max) dataframe:\n{df_out.to_markdown(floatfmt='.3f')}")
        # reset 'site_id'
        df_out["site_id"] = cs.WIZ_KWH["template"]["site_id"]
        # fields 'v1' and 'frq' should be averages
        df_out["v1"] = df_mean["v1"].astype(int)
        df_out["frq"] = df_mean["frq"].astype(int)
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
