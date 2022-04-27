#!/usr/bin/env python3
"""Daemon to periodically call the Myenergy API to fetch energy production data.

Store the data in a SQLite3 database.
"""
import time
import argparse
import configparser
import syslog
import constants
import os
import traceback
import datetime as dt

import mausy5043funcs.fileops3 as mf
import mausy5043libs.libsignals3 as ml
import mausy5043libs.libsqlite3 as m3

import libzappi as zl

parser = argparse.ArgumentParser(description="Execute the zappi daemon.")
parser_group = parser.add_mutually_exclusive_group(required=True)
parser_group.add_argument("--start",
                          action="store_true",
                          help="start the daemon as a service"
                          )
parser_group.add_argument("--debug",
                          action="store_true",
                          help="start the daemon in debugging mode"
                          )
OPTION = parser.parse_args()

# constants
DEBUG = False
HERE = os.path.realpath(__file__).split("/")
# runlist id :
MYID = HERE[-1]
# app_name :
MYAPP = HERE[-3]
MYROOT = "/".join(HERE[0:-3])
# host_name :
NODE = os.uname()[1]

API_ZP = None

# example values:
# HERE: ['', 'home', 'pi', 'lektrix', 'bin', 'zappi.py']
# MYID: zappi.py
# MYAPP: lektrix
# MYROOT: /home/pi
# NODE: rbelec


def main():
    """Execute main loop until killed."""
    global API_ZP
    killer = ml.GracefulKiller()
    iniconf = configparser.ConfigParser()
    # read api_key from the file ~/.config/zappi/keys.ini
    api_keys_file = f"{os.environ['HOME']}/.config/zappi/keys.ini"
    iniconf.read(api_keys_file)
    API_ZP = zl.Myenergi(api_keys_file, DEBUG)

    sql_db = m3.SqlDatabase(database=constants.SOLAREDGE['database'],
                            table='production', insert=constants.SOLAREDGE['sql_command'],
                            debug=DEBUG
                            )

    report_time = int(constants.SOLAREDGE['report_time'])
    sample_time = report_time / int(constants.SOLAREDGE['samplespercycle'])

    site_list = []
    pause_time = 0
    next_time = pause_time + time.time()
    while not killer.kill_now:
        API_ZP.fetch_data(dt.datetime.today())
        print(API_ZP.zappi_data)
        zappi_status = API_ZP.get_status(f"cgi-jstatus-Z{API_ZP.zappi_serial}")
        for k in zappi_status["zappi"][0]:
            print(f"{k}\t::  {zappi_status['zappi'][0][k]}")
        time.sleep(5.0)


if __name__ == "__main__":
    # initialise logging
    syslog.openlog(ident=f'{MYAPP}.{MYID.split(".")[0]}', facility=syslog.LOG_LOCAL0)

    if OPTION.debug:
        DEBUG = True
        mf.syslog_trace("Debug-mode started.", syslog.LOG_DEBUG, DEBUG)
        print("Use <Ctrl>+C to stop.")

    # OPTION.start only executes this next line, we don't need to test for it.
    main()

    print("And it's goodnight from him")
