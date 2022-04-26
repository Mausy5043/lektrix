#!/usr/bin/env python3

import configparser
import datetime as dt
import json
import os
import time
from pprint import pprint
import mausy5043funcs.fileops3 as mf
import traceback
import syslog

import numpy as np
import pandas as pd
import requests
from requests.auth import HTTPDigestAuth

import constants

pd.options.display.float_format = "{:.3f}".format

# constants
HERE = os.path.realpath(__file__).split('/')
# runlist id :
MYID = HERE[-1]
# app_name :
MYAPP = HERE[-3]
MYROOT = '/'.join(HERE[0:-3])
# host_name :
NODE = os.uname()[1]


# CONFIG_FILE = os.environ["HOME"] + "/.config/kamstrup/key.ini"

class Myenergi:
    """Class to interact with the myenergi servers
    """

    def __init__(self, keys_file, debug=False):
        """Initialise the Myenergi object

        Args:
            keys_file (str): full path and filename to a file containing the API-keys (see below).
            debug (bool, optional): [description]. Defaults to False.

        The ini-file must be a configparser compatible file containing:
        [HUB]
        serial: 12345678
        password: secret_hub_password

        [ZAPPI]
        serial: 12345678

        [HARVI]
        serial: 12345678

        [EDDI]
        serial: 12345678
        # EOF
        """
        self.DEBUG = debug
        self.base_url = constants.ZAPPI['director']
        self.zappi_data_template = constants.ZAPPI['template']

        iniconf = configparser.ConfigParser()
        iniconf.read(keys_file)
        self.harvi_serial = iniconf.get("HARVI", "serial")
        self.hub_serial = iniconf.get("HUB", "serial")
        self.hub_username = iniconf.get("HUB", "username")
        self.hub_password = iniconf.get("HUB", "password")
        self.zappi_serial = iniconf.get("ZAPPI", "serial")
        try:
            self.eddi_serial = iniconf.get("EDDI", "serial")
        except configparser.Error:
            mf.syslog_trace(traceback.format_exc(), syslog.LOG_WARNING, self.DEBUG)
            # not everybody has an eddi
            self.eddi_serial = None
            pass

        # First call to the API to get the ASN
        self.response = requests.get(self.base_url,
                                     auth=HTTPDigestAuth(self.hub_serial, self.hub_password)
                                     )
        if self.DEBUG:
            print("Response :")
            pprint(self.response)
            print("")
            for key in self.response.headers:
                print(f"{key}\t  ::  {self.response.headers[key]}")
            print("")

        # construct the URL for the ASN
        if "X_MYENERGI-asn" in self.response.headers:
            self.asn = self.response.headers['X_MYENERGI-asn']
            self.base_url = "https://" + self.asn
            if self.DEBUG:
                print(f"ASN:              {self.asn}")
                print(f"Constructed URL : {self.base_url}")
        else:
            print("myenergi ASN not found in myenergi header")

    def get_status(self, command):
        """Call the API with a command and return the resulting data in a dict.

        Args:
            command (str): command to call the API with.

        Returns:
            (dict): If succesfull, a dict that contains the requested data.
        """
        hdrs = {"User-Agent": "Wget/1.20 (linux-gnu)"}

        call_url = "/".join([self.base_url, command])
        if self.DEBUG:
            print(call_url)
        try:
            response = requests.get(call_url,
                                    headers=hdrs,
                                    auth=HTTPDigestAuth(self.hub_serial, self.hub_password),
                                    timeout=10,
                                    )
        except requests.exceptions.ReadTimeout:
            # We raise the time-out here. If desired, retries should be handled by caller
            print("!!! TimeOut")
            raise
        result = json.loads(response.content)

        if self.DEBUG:
            print(response.status_code)
            for key in response.headers:
                print(key, "  ::  ", response.headers[key])
            print(f"### Payload {command}")
            pprint(result)
            print("***************")

        return result

    def standardise_json_block(self, block):
        """Standardise a block of data from the zappi

        Args:
            block (dict): example; one or more entries of:
                            {'hr': 18,
                             'dow': 'Tue',
                             'dom': 27,
                             'mon': 7,
                             'yr': 2021,
                             'imp': 893760,
                             'gep': 69900,
                             'gen': 3060,
                             'h1b': 1080,
                             'h1d': 5742
                            }

        Returns:
            (dict): values for each parameter in the template. 0 for missing values.
                    Joules are converted to kWh. Datetime parameters are converted to
                    a datetime-object.
        """
        unknown_keys = set()
        for key in self.zappi_data_template:
            if key not in block:
                block[key] = self.zappi_data_template[key]
        for key in block:
            if key not in self.zappi_data_template:
                unknown_keys.add(key)
        if unknown_keys:
            print(" *** Missing keys in template:", unknown_keys)

        return block

    def standardise_data_block(self, block):
        """Standardise a block of data from the zappi

        Args:
            block (dict): example; one or more entries of:
                            {'hr': 18,
                             'dow': 'Tue',
                             'dom': 27,
                             'mon': 7,
                             'yr': 2021,
                             'imp': 893760,
                             'gep': 69900,
                             'gen': 3060,
                             'h1b': 1080,
                             'h1d': 5742
                            }

        Returns:
            (dict): values for each parameter in the template. 0 for missing values.
                    Joules are converted to kWh. Datetime parameters are converted to
                    a datetime-object.
        """
        unknown_keys = set()
        for key in self.zappi_data_template:
            if key not in block:
                block[key] = self.zappi_data_template[key]
        for key in block:
            if key not in self.zappi_data_template:
                unknown_keys.add(key)
        if unknown_keys:
            print(" *** Missing keys in template:", unknown_keys)
        # Convert Joules to kWh
        exp = int(block["exp"] / 3600) / 1000  # exported
        imp = int(block["imp"] / 3600) / 1000  # imported
        # PV production (generator positive)
        gep = int(block["gep"] / 3600) / 1000
        gen = int(block["gen"] / 3600) / 1000  # PV usage (generator negative)
        h1b = int(block["h1b"] / 3600) / 1000  # phase 1 usage (imported)
        h1d = int(block["h1d"] / 3600) / 1000  # phase 1 usage (PV diverted)
        # date is in UTC
        block_dt = f"{str(block['mon']).zfill(2)}" \
                   f"-{str(block['dom']).zfill(2)}" \
                   f" {str(block['hr']).zfill(2)}h"
        # datetime object in UTC
        utc_dt = dt.datetime.strptime(f"{str(block['yr']).zfill(4)}"
                                      f"-{str(block['mon']).zfill(2)}"
                                      f"-{str(block['dom']).zfill(2)}"
                                      f" {str(block['hr']).zfill(2)}:00:00",
                                      "%Y-%m-%d %H:%M:%S"
                                      )

        return {'dat': block_dt,
                'exp': exp,
                'imp': imp,
                'gen': gen,
                'gep': gep,
                'h1b': h1b,
                'h1d': h1d,
                'utc': utc_dt
                }

    def fetch_data(self, day_to_fetch):
        """Fetch data from the API for <day_to_fetch>.

           This will fetch at least 24 hours and including the previous day to compensate
           any hours that might be lost due to the offset from UTC.
           The dates are converted to local time and the data returned is
           for 00:00 u/i 23:59 LOCAL CLOCK TIME of the requested <day_to_fetch>

            Args:
                day_to_fetch (datetime.date): object containing the day for which to fetch data

            Returns:
                (tuple of lists): data for each parameter in a separate list.
        """
        previous_day_data = [self.standardise_json_block(block)
                             for block in self._fetch(day_to_fetch - dt.timedelta(days=1)
                                                      )[f"U{self.zappi_serial}"]
                             ]
        current_day_data = [self.standardise_json_block(block)
                            for block in self._fetch(day_to_fetch)[f"U{self.zappi_serial}"]
                            ]
        pd_data = pd.concat([pd.json_normalize(previous_day_data).fillna(0),
                             pd.json_normalize(current_day_data).fillna(0)
                             ])
        # convert the energy fields from J to kWh
        pd_data['imp'] = joules2kwh(pd_data['imp'])
        pd_data['exp'] = joules2kwh(pd_data['exp'])
        pd_data['gen'] = joules2kwh(pd_data['gen'])
        pd_data['gep'] = joules2kwh(pd_data['gep'])
        pd_data['h1b'] = joules2kwh(pd_data['h1b'])
        pd_data['h1d'] = joules2kwh(pd_data['h1d'])
        # hours are returned as floats. So, first convert float to int
        hours = np.array(pd_data['hr'], dtype=int)
        # then int to str
        hours = np.array(hours, dtype=str)
        # and add a leading zero
        pd_data['hr'] = np.char.zfill(hours, 2)
        # Concatenate date/time parameters to UTC date/time string
        utc_cols = ['yr', 'mon', 'dom']
        pd_data['utc'] = pd_data[utc_cols].apply(lambda row: '-'.join(row.values.astype(str)), axis=1)
        utc_cols = ['utc', 'hr']
        pd_data['utc'] = pd_data[utc_cols].apply(lambda row: ' '.join(row.values.astype(str)) + ":00:00", axis=1)
        pd_data['utc'] = pd.to_datetime(pd_data['utc'], format="%Y-%m-%d %H:%M:%S", utc=True)
        # convert UTC to `sample_time`
        pd_data['sample_time'] = pd_data['utc'].dt.tz_convert('Europe/Amsterdam')
        pd_data.index = pd_data['sample_time']
        # calculate `sample_epoch`
        pd_data['sample_epoch'] = (pd.to_datetime(pd_data['utc']).apply(lambda x: x.value) / 10 ** 9).astype(np.int64)
        # prune the data; throw away what we no longer need.
        pd_data.drop(['dow', 'dom', 'hr', 'mon', 'yr', 'utc'], axis=1, inplace=True)
        if self.DEBUG:
            print(pd_data)

        # TODO: remove LEGACY
        # #### LEGACY code block start
        data_lbls = list()
        imp = list()
        gep = list()
        gen = list()
        exp = list()
        h1b = list()
        h1d = list()
        dtm = list()

        for block in previous_day_data + current_day_data:
            block_values = self.standardise_data_block(block)
            data_lbls.append(block_values['dat'])
            imp.append(block_values['imp'])
            gep.append(block_values['gep'])
            gen.append(block_values['gen'])
            exp.append(block_values['exp'])
            h1b.append(block_values['h1b'])
            h1d.append(block_values['h1d'])
            dtm.append(utc_to_local(block_values['utc']))
        # #### LEGACY code block end
        return data_lbls, imp, gep, gen, exp, h1b, h1d, dtm, pd_data

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
                result = self.get_status(f"cgi-jdayhour-Z{self.zappi_serial}-"
                                         f"{this_day.year}-"
                                         f"{this_day.month}-"
                                         f"{this_day.day}"
                                         )
                done_flag = True
            except requests.exceptions.ReadTimeout:
                timeout_retries -= 1
                if timeout_retries <= 0:
                    # done_flag = False
                    raise
                else:
                    # back off from the server for a while
                    time.sleep(23)
        return result


def utc_to_local(dt_obj):
    """Convert a (UTC) datetime object to local time

    Args:
        dt_obj (datetime.datetime): object to convert (in UTC)

    Returns:
        (datetime.datetime): converted datetime object (local time)
    """
    delta = dt_obj - dt.datetime(1970, 1, 1)
    utc_epoch = (24 * 60 * 60) * delta.days + delta.seconds
    time_struct = time.localtime(utc_epoch)
    dt_args = time_struct[:6] + (delta.microseconds,)
    return dt.datetime(*dt_args)


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
