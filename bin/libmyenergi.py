#!/usr/bin/env python3

# lektrix
# Copyright (C) 2024  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

import configparser
import contextlib
import datetime as dt
import json
import logging
import os
import sys
import time

import constants
import numpy as np
import pandas as pd
import pytz
import requests
from requests.auth import HTTPDigestAuth

LOGGER: logging.Logger = logging.getLogger(__name__)
pd.options.display.float_format = "{:.3f}".format

# constants
HERE: list[str] = os.path.realpath(__file__).split("/")
# runlist id :
MYID: str = HERE[-1]
# app_name :
MYAPP: str = HERE[-3]
MYROOT: str = "/".join(HERE[0:-3])
# host_name :
NODE: str = os.uname()[1]


# CONFIG_FILE = os.environ["HOME"] + "/.config/kamstrup/key.ini"


class Myenergi:  # pylint: disable=too-many-instance-attributes
    """Class to interact with the myenergi servers"""

    def __init__(self, keys_file: str, debug=False) -> None:
        """Initialise the Myenergi object.

        The keys-file must be a configparser compatible file containing:
        [API]
        api_key: secret_api_key
        [HUB]
        serial: 12345678
        [ZAPPI]
        serial: 12345678
        [HARVI]
        serial: 12345678
        [EDDI]
        serial: 12345678
        [LIBBI]
        serial: 12345678
        <EOF>

        Args:
            keys_file (str): full path and filename to a file containing
                             the serialnumbers and API-key (see below).
            debug (bool, optional): [description]. Defaults to False.

        Atrtributes:
            DEBUG (bool): show debugging info
            zappi_data (list): list of dicts containing the data
        """
        self.DEBUG: bool = debug
        self.base_url: str = constants.ZAPPI["director"]
        self.zappi_data: list = []
        self.zappi_data_template = constants.ZAPPI["template"]

        iniconf = configparser.ConfigParser()
        iniconf.read(keys_file)
        self.api_key: str = self.get_key(iniconf, "API", "api_key")
        self.harvi_serial: str = self.get_key(iniconf, "HARVI", "serial")
        self.hub_serial: str = self.get_key(iniconf, "HUB", "serial")
        self.zappi_serial: str = self.get_key(iniconf, "ZAPPI", "serial")
        self.eddi_serial: str = self.get_key(iniconf, "EDDI", "serial")
        self.libbi_serial: str = self.get_key(iniconf, "LIBBI", "serial")

        # First call to the API to get the ASN
        _response = requests.get(  # nosec B113
            self.base_url,
            auth=HTTPDigestAuth(self.hub_serial, self.api_key),
            timeout=constants.ZAPPI["requests_timeout"],
        )
        if debug:
            if len(LOGGER.handlers) == 0:
                LOGGER.addHandler(logging.StreamHandler(sys.stdout))
            LOGGER.level = logging.DEBUG
            LOGGER.debug("Debugging on.")
            LOGGER.debug(f"Response Status Code: {_response.status_code}")
            for key in _response.headers:
                LOGGER.debug(f"   {key} :: {_response.headers[key]}")
            LOGGER.debug("***** ***** *****")

        # construct the URL for the ASN
        if "X_MYENERGI-asn" in _response.headers:
            _asn = _response.headers["X_MYENERGI-asn"]
            self.base_url = "https://" + _asn
            LOGGER.info(f"ASN             : {_asn}")
            LOGGER.info(f"Constructed URL : {self.base_url}")
        else:
            raise RuntimeError("myenergi ASN not found in myenergi header")

    def get_key(self, confobj, key_section: str, key_option: str) -> str:
        """Read keys from keys_file with error handling

        Args:
            confobj (obj):  configparser object
            key_section (str): section name
            key_option (str): option name

        Returns:
            value of the option
        """
        key_value: str = ""
        try:
            key_value = confobj.get(key_section, key_option)
        except configparser.NoSectionError:
            LOGGER.warning(f"Section [{key_section}] does not exist.")
        except configparser.NoOptionError:
            LOGGER.warning(f"Option [{key_section}]\n{key_option} = ...\ndoes not exist.")
        return key_value

    def get_status(self, command: str) -> dict:
        """Call the API with a command and return the resulting data in a dict.

        Args:
            command (str): command to call the API with.

        Returns:
            (dict): If succesfull, a dict that contains the requested data.
        """
        result: dict = {}
        hdrs: dict = {"User-Agent": "Wget/1.20 (linux-gnu)"}
        call_url: str = f"{self.base_url}/{command}"
        LOGGER.debug(f"Calling {call_url}")
        try:
            response = requests.get(  # nosec B113
                call_url,
                headers=hdrs,
                auth=HTTPDigestAuth(self.hub_serial, self.api_key),
                timeout=10,
            )
        except requests.exceptions.ReadTimeout:
            # We raise the time-out here. If desired, retries should be handled by caller
            LOGGER.warning(f"{call_url} timed out!")
            raise
        if self.DEBUG:
            LOGGER.debug(f"Response Status Code: {response.status_code}")
            for key in response.headers:
                LOGGER.debug(f"   {key} :: {response.headers[key]}")
            LOGGER.debug("***** ***** *****")

        try:
            result = json.loads(response.content)
        except json.decoder.JSONDecodeError:
            LOGGER.critical("Could not load JSON data.")
            return result
        # LOGGER.debug(f"{result}")
        return result

    def standardise_json_block(self, blk) -> dict:
        """Standardise a block of data from the myenergi DB

        Args:
            blk (dict): dict containing one entry from the myenergi database

        Returns:
            (dict): values for each parameter in the template. 0 for missing values.
                    Joules are converted to kWh. Date and time parameters are converted to
                    a datetime-string and epoch-value in the local timezone.
        """
        result_dict: dict = {}
        for _key, _value in self.zappi_data_template.items():
            try:
                result_dict[_key] = blk[_key]
            except KeyError:
                result_dict[_key] = _value

        utc_date_time: dt.datetime = dt.datetime.strptime(
            f"{result_dict['yr']}-{result_dict['mon']:02d}-{result_dict['dom']:02d} "
            f"{result_dict['hr']:02d}:{result_dict['min']:02d}:00",
            constants.DT_FORMAT,
        )  # UTC!
        # discard fields we nolonger need
        for _key in constants.ZAPPI["template_keys_to_drop"]:
            with contextlib.suppress(KeyError):
                del result_dict[_key]
        # convert the UTC time from MyEnergi to local time
        lcl_date_time: dt.datetime = utc_date_time.replace(tzinfo=pytz.utc)
        lcl_date_time = lcl_date_time.astimezone(constants.TIMEZONE)
        date_time: str = lcl_date_time.strftime(constants.DT_FORMAT)
        result_dict["sample_time"] = date_time
        result_dict["sample_epoch"] = int(
            dt.datetime.strptime(date_time, constants.DT_FORMAT).timestamp()
        )

        # LOGGER.debug(f"> {result_dict}")
        return result_dict

    def fetch_data(self, day_to_fetch: dt.datetime) -> None:
        """Fetch data from the API for <day_to_fetch> and store it as a list of dicts
        in `zappi_data`.

        This will fetch at least 24 hours and including the previous day to compensate for
        any hours that might be lost due to the offset from UTC.
        The dates are converted to local time and the data returned is
        for 00:00 u/i 23:59 LOCAL CLOCK TIME of the requested <day_to_fetch>

         Args:
             day_to_fetch (datetime.date): object containing the day for which to fetch data

         Returns:
             None
        """
        self.zappi_data = []
        result: list = []
        _dif: dt.timedelta = dt.datetime.now() - day_to_fetch
        extra_day1_data: list = []
        previous_day_data: list = []
        current_day_data: list = []
        # fmt: off
        # pylint: disable=line-too-long
        try:
            if (_dif.days) < 7:
                extra_day1_data = [self.standardise_json_block(block) for block in self._fetch(day_to_fetch - dt.timedelta(days=2.0))[f"U{self.zappi_serial}"]]
                previous_day_data = [self.standardise_json_block(block) for block in self._fetch(day_to_fetch - dt.timedelta(days=1.0))[f"U{self.zappi_serial}"]]
            current_day_data = [self.standardise_json_block(block) for block in self._fetch(day_to_fetch)[f"U{self.zappi_serial}"]]

            # LOGGER.debug(f"> {extra_day1_data[0]}")
            # LOGGER.debug(f"> {extra_day1_data[1]}")
            # LOGGER.debug(f"> {previous_day_data[0]}")
            # LOGGER.debug(f"> {previous_day_data[1]}")
            # LOGGER.debug(f"> {current_day_data[-2]}")
            # LOGGER.debug(f"> {current_day_data[-1]}")
        except IndexError:
            LOGGER.warning(f"IndexError encountered for {day_to_fetch.strftime(format=constants.DT_FORMAT)}")
        except KeyError:
            LOGGER.warning(f"KeyError encountered for {day_to_fetch.strftime(format=constants.DT_FORMAT)}")
        # fmt: on
        result = extra_day1_data + previous_day_data + current_day_data
        self.zappi_data = self.compact_data(result)

    def _fetch(self, this_day: dt.date) -> dict:
        """Try to get the data off the server for the date <this_day>.

        Args:
            this_day (datetime.date): datetime to get data for

        Returns:
            (dict): whatever was returned by the server (probably a dict)
        """

        LOGGER.debug(f">> Asking for data from {this_day}")
        result = {}
        done_flag = False
        timeout_retries = 3
        while not done_flag:
            try:
                # hourly data
                # result = self.get_status(f"cgi-jdayhour-Z{self.zappi_serial}-"
                # minutely data
                # result = self.get_status(f"cgi-jday-Z{self.zappi_serial}-"
                result = self.get_status(
                    f"cgi-jday-Z{self.zappi_serial}-"
                    f"{this_day.year}-"
                    f"{this_day.month}-"
                    f"{this_day.day}"
                )
                done_flag = True
            except requests.exceptions.ReadTimeout:
                LOGGER.warning("Timeout receiving data from server")
                timeout_retries -= 1
                if timeout_retries <= 0:
                    # raise for testing
                    # done_flag = False
                    raise
                # back off from the server for a while
                time.sleep(23)
        return result

    def compact_data(self, data) -> list:
        """
        Compact the one-minute data into 15-minute data

        Args:
            data (list): list of dicts containing one-minute data from myenergy DB

        Returns:
            (list): list of dicts containing compacted data
        """

        def _convert_time_to_epoch(date_to_convert) -> int:
            _res: int = int(pd.Timestamp(date_to_convert).timestamp())
            return _res

        def _convert_time_to_text(date_to_convert) -> str:
            _res: str = pd.Timestamp(date_to_convert).strftime(constants.DT_FORMAT)
            return _res

        result_data: list = []

        if data:
            df: pd.DataFrame = pd.DataFrame(data)
            df = df.set_index("sample_time")
            df.index = pd.to_datetime(df.index, format=constants.DT_FORMAT, utc=False)
            # resample to monotonic timeline
            df = df.resample("15min", label="right").sum()
            # recreate column 'sample_time' that was lost to the index
            df["sample_time"] = df.index.to_frame(name="sample_time")
            df["sample_time"] = df["sample_time"].apply(_convert_time_to_text)
            # reset 'site_id'
            df["site_id"] = 4.1
            # fields 'v1' and 'frq' should be averaged so divide them by 15 here:
            df["v1"] = np.array(df["v1"] / 15, dtype="int")
            df["frq"] = np.array(df["frq"] / 15, dtype="int")
            # recalculate 'sample_epoch'
            df["sample_epoch"] = df["sample_time"].apply(_convert_time_to_epoch)
            LOGGER.debug(f"{df.to_markdown()}")
            result_data = df.to_dict("records")
        return result_data


def joules2kwh(df_joules) -> np.ndarray:
    """Convert Joules to kWh values

    Args:
        df_joules (Any): data in [J]

    Returns:
        (numpy.ndarray): data in [kWh]
    """
    df_wh: np.ndarray = np.array(df_joules / 3600, dtype=int)
    for k, v in enumerate(df_wh):
        if v < 10:
            df_wh[k] = 0
    df_kwh: np.ndarray = np.array(df_wh / 1000)
    return df_kwh
