#!/usr/bin/env python3

import configparser
import datetime as dt
import json
import os
import syslog
import time

import mausy5043_common.funfile as mf
import numpy as np
import pandas as pd
import pytz
import requests
from requests.auth import HTTPDigestAuth

import constants

pd.options.display.float_format = "{:.3f}".format

# constants
HERE = os.path.realpath(__file__).split("/")
# runlist id :
MYID = HERE[-1]
# app_name :
MYAPP = HERE[-3]
MYROOT = "/".join(HERE[0:-3])
# host_name :
NODE = os.uname()[1]


# CONFIG_FILE = os.environ["HOME"] + "/.config/kamstrup/key.ini"


class Myenergi:
    """Class to interact with the myenergi servers"""

    def __init__(self, keys_file, debug=False):
        r"""Initialise the Myenergi object.

        The keys-file must be a configparser compatible file containing:\n
        [HUB]\n
        serial: 12345678\n
        password: secret_hub_password\n
        [ZAPPI]\n
        serial: 12345678\n
        [HARVI]\n
        serial: 12345678\n
        [EDDI]\n
        serial: 12345678\n
        <EOF>

        Args:
            keys_file (str): full path and filename to a file containing the API-keys (see below).
            debug (bool, optional): [description]. Defaults to False.


        Atrtributes:
            DEBUG (bool): show debugging info
            zappi_data (list): list of dicts containing the data

        """
        self.DEBUG = debug
        self.base_url = constants.ZAPPI["director"]
        self.zappi_data = list()
        self.zappi_data_template = constants.ZAPPI["template"]

        iniconf = configparser.ConfigParser()
        iniconf.read(keys_file)
        self.harvi_serial = self.get_key(iniconf, "HARVI", "serial")
        self.hub_serial = self.get_key(iniconf, "HUB", "serial")
        self.hub_username = self.get_key(iniconf, "HUB", "username")
        self.hub_password = self.get_key(iniconf, "HUB", "password")
        self.zappi_serial = self.get_key(iniconf, "ZAPPI", "serial")
        self.eddi_serial = self.get_key(iniconf, "EDDI", "serial")

        # First call to the API to get the ASN
        _response = requests.get(
            self.base_url, auth=HTTPDigestAuth(self.hub_serial, self.hub_password)
        )
        if self.DEBUG:
            mf.syslog_trace(f"Response Status Code : {_response.status_code}", False, self.DEBUG)
            for key in _response.headers:
                mf.syslog_trace(f"   {key}\t::\t{_response.headers[key]}", False, self.DEBUG)
            mf.syslog_trace("", False, self.DEBUG)

        # construct the URL for the ASN
        if "X_MYENERGI-asn" in _response.headers:
            _asn = _response.headers["X_MYENERGI-asn"]
            self.base_url = "https://" + _asn
            mf.syslog_trace(f"ASN             : {_asn}", syslog.LOG_INFO, self.DEBUG)
            mf.syslog_trace(f"Constructed URL : {self.base_url}", syslog.LOG_INFO, self.DEBUG)
        else:
            raise RuntimeError("myenergi ASN not found in myenergi header")

    def get_key(self, confobj, key_section, key_option):
        """Read keys from keys_file with error handling

        Args:
            confobj (obj):  configparser object
            key_section (str): section name
            key_option (str): option name

        Returns:
            value of the option
        """
        key_value = None
        try:
            key_value = confobj.get(key_section, key_option)
        except configparser.NoSectionError:
            mf.syslog_trace(
                f"Section [{key_section}] does not exist.",
                syslog.LOG_WARNING,
                self.DEBUG,
            )
            pass
        except configparser.NoOptionError:
            mf.syslog_trace(
                f"Option [{key_section}]\n{key_option} = ...    does not exist.",
                syslog.LOG_WARNING,
                self.DEBUG,
            )
            pass
        return key_value

    def get_status(self, command):
        """Call the API with a command and return the resulting data in a dict.

        Args:
            command (str): command to call the API with.

        Returns:
            (dict): If succesfull, a dict that contains the requested data.
        """
        hdrs = {"User-Agent": "Wget/1.20 (linux-gnu)"}

        call_url = "/".join([self.base_url, command])
        mf.syslog_trace(f"Calling {call_url}", False, self.DEBUG)
        try:
            response = requests.get(
                call_url,
                headers=hdrs,
                auth=HTTPDigestAuth(self.hub_serial, self.hub_password),
                timeout=10,
            )
        except requests.exceptions.ReadTimeout:
            # We raise the time-out here. If desired, retries should be handled by caller
            mf.syslog_trace(f"{call_url} timed out!", syslog.LOG_WARNING, self.DEBUG)
            raise
        if self.DEBUG:
            mf.syslog_trace(f"Response Status Code: {response.status_code}", False, self.DEBUG)
            for key in response.headers:
                mf.syslog_trace(f"   {key} :: {response.headers[key]}", False, self.DEBUG)
            mf.syslog_trace("***** ***** *****", False, self.DEBUG)

        try:
            result = json.loads(response.content)
        except json.decoder.JSONDecodeError:
            mf.syslog_trace(f"Could not load JSON data.", syslog.LOG_ERR, self.DEBUG)
            return None

        return result

    def standardise_json_block(self, blk):
        """Standardise a block of data from the myenergi DB

        Args:
            blk (dict): dict containing one entry from the myenergi database

        Returns:
            (dict): values for each parameter in the template. 0 for missing values.
                    Joules are converted to kWh. Date and time parameters are converted to
                    a datetime-string and epoch-value in the local timezone.
        """
        result_dict = dict()
        for key in self.zappi_data_template:
            try:
                result_dict[key] = blk[key]
            except KeyError:
                result_dict[key] = self.zappi_data_template[key]

        utc_date_time = dt.datetime.strptime(
            f"{result_dict['yr']}-{result_dict['mon']:02d}-{result_dict['dom']:02d} "
            f"{result_dict['hr']:02d}:{result_dict['min']:02d}:00",
            constants.DT_FORMAT,
        )  # UTC!
        # if result_dict['min'] == 0:
        #     mf.syslog_trace(f"|---  {utc_date_time.strftime(constants.DT_FORMAT)}  ---", False, self.DEBUG)
        # discard fields we nolonger need
        for key in constants.ZAPPI["template_keys_to_drop"]:
            try:
                del result_dict[key]
            except KeyError:
                pass
        # convert the UTC time from MyEnergi to local time
        lcl_date_time = utc_date_time.replace(tzinfo=pytz.utc)
        lcl_date_time = lcl_date_time.astimezone(constants.TIMEZONE)
        date_time = lcl_date_time.strftime(constants.DT_FORMAT)
        result_dict["sample_time"] = date_time
        result_dict["sample_epoch"] = int(
            dt.datetime.strptime(date_time, constants.DT_FORMAT).timestamp()
        )

        # mf.syslog_trace(f"> {result_dict}", False, self.DEBUG)
        return result_dict

    def fetch_data(self, day_to_fetch):
        """Fetch data from the API for <day_to_fetch> and store it as a list of dicts in `zappi_data`

        This will fetch at least 24 hours and including the previous day to compensate for
        any hours that might be lost due to the offset from UTC.
        The dates are converted to local time and the data returned is
        for 00:00 u/i 23:59 LOCAL CLOCK TIME of the requested <day_to_fetch>

         Args:
             day_to_fetch (datetime.date): object containing the day for which to fetch data

         Returns:
             None
        """
        self.zappi_data = list()
        result = list()
        previous_day_data = [
            self.standardise_json_block(block)
            for block in self._fetch(day_to_fetch - dt.timedelta(days=1))[
                f"U{self.zappi_serial}"
            ]
        ]
        current_day_data = [
            self.standardise_json_block(block)
            for block in self._fetch(day_to_fetch)[f"U{self.zappi_serial}"]
        ]
        try:
            mf.syslog_trace(f"> {previous_day_data[0]}", False, self.DEBUG)
            mf.syslog_trace(f"> {previous_day_data[1]}", False, self.DEBUG)
            mf.syslog_trace(f"> {current_day_data[-2]}", False, self.DEBUG)
            mf.syslog_trace(f"> {current_day_data[-1]}", False, self.DEBUG)
        except IndexError:
            pass

        result = previous_day_data + current_day_data
        self.zappi_data = self.compact_data(result)

    def _fetch(self, this_day):
        """Try to get the data off the server for the date <this_date>.

        Args:
            this_day (datetime.date): datetime to get data for

        Returns:
            (dict): whatever was returned by the server (probably a dict)
        """
        result = dict()
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
                timeout_retries -= 1
                if timeout_retries <= 0:
                    # raise for testing
                    # done_flag = False
                    raise
                else:
                    # back off from the server for a while
                    time.sleep(23)
        return result

    def compact_data(self, data):
        """
        Compact the one-minute data into 15-minute data

        Args:
            data (list): list of dicts containing one-minute data from myenergy DB

        Returns:
            (list): list of dicts containing compacted data
        """

        def _convert_time_to_epoch(date_to_convert):
            return int(pd.Timestamp(date_to_convert).timestamp())

        def _convert_time_to_text(date_to_convert):
            return pd.Timestamp(date_to_convert).strftime(constants.DT_FORMAT)

        result_data = list()

        if data:
            df = pd.DataFrame(data)
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
            mf.syslog_trace(f"{df}", False, self.DEBUG)
            result_data = df.to_dict("records")
        return result_data


def joules2kwh(df_joules):
    """Convert Joules to kWh values

    Args:
        df_joules (Any): data in [J]

    Returns:
        (numpy.ndarray): data in [kWh]
    """
    df_wh = np.array(df_joules / 3600, dtype=int)
    for k, v in enumerate(df_wh):
        if v < 10:
            df_wh[k] = 0
    df_kwh = np.array(df_wh / 1000)
    return df_kwh
