#!/usr/bin/env python3

"""Common functions for use with the KAMSTRUP electricity meter"""

import datetime as dt
import re
import syslog
import traceback

import mausy5043funcs.fileops3 as mf
import numpy as np
import pandas as pd
import serial
import sqlite3 as s3

import constants


class Kamstrup:
    """Class to interact with the P1-port
    """

    def __init__(self, debug=False):
        self.PORT = serial.Serial()
        self.PORT.baudrate = 9600
        self.PORT.bytesize = serial.SEVENBITS
        self.PORT.parity = serial.PARITY_EVEN
        self.PORT.stopbits = serial.STOPBITS_ONE
        self.PORT.xonxoff = 1
        self.PORT.rtscts = 0
        self.PORT.dsrdtr = 0
        self.PORT.timeout = 15
        self.PORT.port = "/dev/ttyUSB0"

        self.PORT.open()
        serial.XON  # noqa

        self.dt_format = "%Y-%m-%d %H:%M:%S"
        # starting values
        self.electra1in = np.nan
        self.electra2in = np.nan
        self.electra1out = np.nan
        self.electra2out = np.nan
        self.powerin = np.nan
        self.powerout = np.nan
        self.tarif = 1
        self.swits = 0
        self.list_data = list()

        self.debug = debug
        if self.debug:
            self.telegram = list()

    def get_telegram(self):
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
                mf.syslog_trace("*** Serialport read error:", syslog.LOG_CRIT, self.debug)
                mf.syslog_trace(traceback.format_exc(), syslog.LOG_CRIT, self.debug)
                valid_telegram = False
                receiving = False
                pass
            except UnicodeDecodeError:
                mf.syslog_trace("*** Unicode Decode error:", syslog.LOG_CRIT, self.debug)
                mf.syslog_trace(traceback.format_exc(), syslog.LOG_CRIT, self.debug)
                valid_telegram = False
                receiving = False
                pass

            loops2go = loops2go - 1
            if loops2go < 0:
                receiving = False

        # validate correct start of telegram
        if telegram[0][0] != "/":
            valid_telegram = False

        # store final result
        if valid_telegram:
            if self.debug:
                self.telegram = telegram
                with open("/tmp/kamstrup.raw", "w") as output_file:
                    for line in self.telegram:
                        output_file.write(f"{line}\n")
            self.list_data.append(self._translate_telegram(telegram))
        return valid_telegram

    def _translate_telegram(self, telegram):
        """Translate the telegram to a dict.

        kW or kWh are converted to W resp. kW

        Returns:
            (dict): data converted to a dict.
        """
        for element in telegram:
            try:
                line = re.split(r'[\(\*\)]', element)
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
                # ['0-0:17.0.0', '999', 'A', ''] unknown;
                # not recorded
                # ['0-0:96.3.10', '1', '']  powerusage (1)
                #                           or powermanufacturing ()
                if line[0] == "0-0:96.3.10":
                    self.swits = int(line[1])
                    # swits is not always present. The value will
                    # change *if* present in the telegram.
                # ['0-0:96.13.1', '', '']
                # not recorded
                # ['0-0:96.13.0', '', '']
                # not recorded
            except ValueError:
                if self.debug:
                    mf.syslog_trace("*** Conversion not possible for element:", syslog.LOG_INFO, self.debug)
                    mf.syslog_trace(f"    {element}", syslog.LOG_INFO, self.debug)
                    mf.syslog_trace("*** Extracted from telegram:", syslog.LOG_INFO, self.debug)
                    mf.syslog_trace(f"    {telegram}", syslog.LOG_INFO, self.debug)
                pass
        idx_dt = dt.datetime.now()
        epoch = int(idx_dt.timestamp())

        return {'sample_time': idx_dt.strftime(self.dt_format),
                'sample_epoch': epoch,
                'T1in': self.electra1in,
                'T2in': self.electra2in,
                'powerin': self.powerin,
                'T1out': self.electra1out,
                'T2out': self.electra2out,
                'powerout': self.powerout,
                'tarif': self.tarif,
                'swits': self.swits
                }

    def compact_data(self, data):
        """
        Compact the ten-second data into 15-minute data

        Args:
            data (list): list of dicts containing 10-second data from the electricity meter

        Returns:
            (list): list of dicts containing compacted 15-minute data
        """

        def _convert_time_to_epoch(date_to_convert):
            return int(pd.Timestamp(date_to_convert).timestamp())

        def _convert_time_to_text(date_to_convert):
            return pd.Timestamp(date_to_convert).strftime(constants.DT_FORMAT)

        df = pd.DataFrame(data)
        df = df.set_index('sample_time')
        df.index = pd.to_datetime(df.index, format=constants.DT_FORMAT, utc=False)
        # resample to monotonic timeline
        df_out = df.resample('15min', label='right').max()
        df_mean = df.resample('15min', label='right').mean()

        df_out['powerin'] = df_mean['powerin'].astype(int)
        df_out['powerout'] = df_mean['powerout'].astype(int)
        # recreate column 'sample_time' that was lost to the index
        df_out['sample_time'] = df_out.index.to_frame(name='sample_time')
        df_out['sample_time'] = df_out['sample_time'].apply(_convert_time_to_text)

        # recalculate 'sample_epoch'
        df_out['sample_epoch'] = df_out['sample_time'].apply(_convert_time_to_epoch)
        mf.syslog_trace(f"{df_out}", False, self.debug)
        result_data = df_out.to_dict('records')     # list of dicts
        df = df[df['sample_epoch'] > np.max(df_out['sample_epoch'])]
        remain_data = df.to_dict('records')
        return result_data, remain_data


def add_time_line(config):
    """Create a numpy array of labels based on the settings in config

    Args:
        config (dict): settings to be used

    Returns:
        Modified version of `config`
    """
    final_epoch = int(dt.datetime.now().timestamp())
    if "year" in config:
        ytf = int(config["year"]) + 1
        final_epoch = int(dt.datetime.strptime(f"{ytf}-01-01 00:00", "%Y-%m-%d %H:%M"
                                               ).timestamp()
                          )
    step_epoch = 15 * 60
    multi = 3600
    if config["timeframe"] == "hour":
        multi = 3600
    if config["timeframe"] == "day":
        multi = 3600 * 24
    if config["timeframe"] == "month":
        multi = 3600 * 24 * 31
    if config["timeframe"] == "year":
        multi = 3600 * 24 * 366
    start_epoch = (int((final_epoch
                        - (multi * config["period"])
                        ) / step_epoch
                       ) * step_epoch
                   )
    config["timeline"] = np.arange(start_epoch,
                                   final_epoch,
                                   step_epoch,
                                   dtype="int"
                                   )
    return config


def get_historic_data(dicti, telwerk=None, from_start_of_year=False, include_today=True, dif=True):
    """Fetch historic data from SQLITE3 database.

    Args:
        dif: whether to treat the data as a cumulative counter or as single values
        include_today (bool): whether or not to include today's data
        dicti (dict): containing settings
        telwerk (str): columnname to be collected
        from_start_of_year (bool): fetch data from start of year or not

    Returns:
        ret_data: numpy list of ints - data returned and numpy list of str - label texts returned
    """
    ytf = 2019
    period = dicti["period"]
    interval = f"datetime('now', '-{period + 1} {dicti['timeframe']}')"
    and_where_not_today = ""
    if from_start_of_year:
        interval = f"datetime(datetime('now', '-{period + 1} {dicti['timeframe']}'), 'start of year')"
    if not include_today:
        and_where_not_today = "AND (sample_time <= datetime('now', '-1 day'))"
    if "year" in dicti:
        ytf = dicti["year"]
        interval = f"datetime('{ytf}-01-01 00:00')"
        and_where_not_today = f"AND (sample_time <= datetime('{ytf + 1}-01-01 00:00'))"

    db_con = s3.connect(dicti["database"])
    with db_con:
        db_cur = db_con.cursor()
        db_cur.execute(f"SELECT sample_epoch, "
                       f"{telwerk} "
                       f"FROM {dicti['table']} "
                       f"WHERE (sample_time >= {interval}) "
                       f"{and_where_not_today} "
                       f"ORDER BY sample_epoch ASC "
                       f";"
                       )
        db_data = db_cur.fetchall()
    if not db_data:
        # fake some data
        db_data = [(int(dt.datetime(ytf, 1, 1).timestamp()), 0),
                   (int(dt.datetime(ytf + 1, 1, 1).timestamp()), 0),
                   ]

    data = np.array(db_data)

    # interpolate the data to monotonic 10minute intervals provided by dicti['timeline']
    ret_epoch, ret_intdata = interplate(dicti["timeline"],
                                        np.array(data[:, 0], dtype=int),
                                        np.array(data[:, 1], dtype=int),
                                        )

    # group the data by dicti['grouping']
    ret_lbls, ret_grpdata = fast_group_data(ret_epoch,
                                            ret_intdata,
                                            dicti["grouping"],
                                            dif=dif
                                            )

    ret_data = ret_grpdata / 1000
    return ret_data[-period:], ret_lbls[-period:]


def interplate(epochrng, epoch, data):
    """Interpolate the given data to a neat monotonic dataset
    with 10 minute intervals"""
    datarng = np.interp(epochrng, epoch, data)
    return epochrng, datarng


def contract(arr1, arr2):
    """
    Add two arrays together.
    """
    size = max(len(arr1), len(arr2))
    rev_arr1 = np.zeros(size, dtype=float)
    rev_arr2 = np.zeros(size, dtype=float)
    for idx in range(0, len(arr1)):
        rev_arr1[idx] = arr1[::-1][idx]
    for idx in range(0, len(arr2)):
        rev_arr2[idx] = arr2[::-1][idx]
    result = np.sum([rev_arr1, rev_arr2], axis=0)
    return result[::-1]


def distract(arr1, arr2):
    """
    Subtract two arrays.
    Note: order is important!
    """
    size = max(len(arr1), len(arr2))
    rev_arr1 = np.zeros(size, dtype=float)
    rev_arr2 = np.zeros(size, dtype=float)
    for idx in range(0, len(arr1)):
        rev_arr1[idx] = arr1[::-1][idx]
    for idx in range(0, len(arr2)):
        rev_arr2[idx] = arr2[::-1][idx]
    result = np.subtract(rev_arr1, rev_arr2)
    result[result < 0] = 0.0
    return result[::-1]


def fast_group_data(x_epochs, y_data, grouping, dif=True):
    """A faster version of group_data()."""
    # convert y-values to numpy array
    y_data = np.array(y_data)
    # convert epochs to text
    x_texts = np.array([dt.datetime.fromtimestamp(i).strftime(grouping) for i in x_epochs],
                       dtype="str",
                       )
    """
    x_texts =
    ['12-31 20h' '12-31 21h' '12-31 21h' '12-31 21h' '12-31 21h' '12-31 21h'
     '12-31 21h' '12-31 22h' '12-31 22h' '12-31 22h' '12-31 22h' '12-31 22h'
     :
     '01-01 08h' '01-01 09h' '01-01 09h' '01-01 09h' '01-01 09h' '01-01 09h'
     '01-01 09h' '01-01 10h' '01-01 10h' '01-01 10h' '01-01 10h' '01-01 10h'
     '01-01 10h']
    """
    # compress x_texts to a unique list
    # order must be preserved
    _, loc1 = np.unique(x_texts, return_index=True)
    loc_from = np.sort(loc1)
    unique_x_texts = x_texts[loc1]
    loc2 = (len(x_texts) - 1 - np.unique(np.flip(x_texts),
                                         return_index=True)[1]
            )
    loc_to = np.sort(loc2)

    if not dif:
        # print(y_data)
        # print(loc1, loc2)
        y = []
        for i, v in enumerate(loc1):
            # f1 = y_data[v:loc2[i]]
            # print(i, v, loc2[i], f1, f1.sum())
            y.append(y_data[v:loc2[i]].sum())
        y = np.array(y)
    if dif:
        y = y_data[loc_to] - y_data[loc_from]

    returned_y_data = np.where(y > 0, y, 0)

    return unique_x_texts, returned_y_data


def build_arrays44(lbls, use_data, expo_data):
    """Use the input to build two arrays and return them.
    example input line : "2015-01; 329811; 0"  : YYYY-MM; T1; T2
    the list comes ordered by the first field
    the first line and last line can be inspected to find
    the first and last year in the dataset.
    """
    first_year = int(lbls[0].split("-")[0])
    last_year = int(lbls[-1].split("-")[0]) + 1
    num_years = last_year - first_year

    label_lists = [np.arange(first_year, last_year), np.arange(1, 13)]
    usage = np.zeros((num_years, 12))
    exprt = np.zeros((num_years, 12))

    for data_point in zip(lbls, use_data, expo_data):
        [year, month] = data_point[0].split("-")
        col_idx = int(month) - 1
        row_idx = int(year) - first_year
        usage[row_idx][col_idx] = data_point[1]
        exprt[row_idx][col_idx] = data_point[2]
    return label_lists, usage, exprt
