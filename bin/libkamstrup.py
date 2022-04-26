#!/usr/bin/env python3

"""Common functions for use with the KAMSTRUP electricity meter"""

import datetime as dt
import re
import syslog
import traceback

import mausy5043funcs.fileops3 as mf
import numpy as np
import serial   # noqa


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
            valid telegram received (bool)
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
                # ['0-0:17.0.0', '999', 'A', ''] unknown; not recorded
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