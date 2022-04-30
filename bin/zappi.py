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

    sql_db = m3.SqlDatabase(database=constants.ZAPPI['database'],
                            table='charger', insert=constants.ZAPPI['sql_command'],
                            debug=DEBUG
                            )

    report_time = int(constants.ZAPPI['report_time'])
    sample_time = report_time / int(constants.ZAPPI['samplespercycle'])

    pause_time = 0
    next_time = pause_time + time.time()
    while not killer.kill_now:
        if time.time() > next_time:
            start_time = time.time()

            try:
                data = do_work(API_ZP)
            except Exception:   # noqa
                mf.syslog_trace("Unexpected error while try to do some work!", syslog.LOG_CRIT, DEBUG)
                mf.syslog_trace(traceback.format_exc(), syslog.LOG_CRIT, DEBUG)
                raise
            if data:
                try:
                    mf.syslog_trace(f"Data to add : {data}", False, DEBUG)
                    for element in data:
                        sql_db.queue(element)
                except Exception:   # noqa
                    mf.syslog_trace("Unexpected error while try to queue the data", syslog.LOG_ALERT, DEBUG)
                    mf.syslog_trace(traceback.format_exc(), syslog.LOG_ALERT, DEBUG)
                    raise   # may be changed to pass if errors can be corrected.
                try:
                    sql_db.insert()
                except Exception:   # noqa
                    mf.syslog_trace("Unexpected error while try to commit the data to the database",
                                    syslog.LOG_ALERT, DEBUG)
                    mf.syslog_trace(traceback.format_exc(), syslog.LOG_ALERT, DEBUG)
                    raise   # may be changed to pass if errors can be corrected.

            pause_time = (sample_time
                          - (time.time() - start_time)          # time spent in this loop           eg. (40-3) = 37s
                          - (start_time % sample_time)          # number of seconds to next loop    eg. 3 % 60 = 3s
                          )
            next_time = pause_time + time.time()                # gives the actual time when the next loop should start
            """Example calculation:
            sample_time = 60s   # target duration one loop
            time.time() = 40    # actual current time
            start_time = 3      # actual current time when the loop was started

            sample_time - ( time.time() - start_time ) - ( start_time % sample_time )
                60      - (     40      -     3      ) - (     3      %    60       )
                60      -             37               -            3
             = 20 s waiting time

            Example 2:
                60      - (     181     -     122      ) - (     122      %    60       )
                60      -             59                -            2
             = 3 seconds behind (no waiting)
            """
            if pause_time > 0:
                mf.syslog_trace(f"Waiting  : {pause_time:.1f}s", False, DEBUG, )
                mf.syslog_trace("................................", False, DEBUG)
            else:
                mf.syslog_trace(f"Behind   : {pause_time:.1f}s", False, DEBUG, )
                mf.syslog_trace("................................", False, DEBUG)
        else:
            time.sleep(1.0)     # 1s resolution is enough


def do_work(zappi):
    zappi.fetch_data(dt.datetime.today())   # TODO: start with the last date in the DB

    """
     {'sample_time': '2022-04-30 08:37:00', 'sample_epoch': 1651300620, 'site_id': 4.1,
      'exp': 300, 'gen': 0.0, 'gep': 24180, 'imp': 1860, 'h1b': 0.0, 'h1d': 0.0,
      'v1': 2245, 'frq': 5001
     }
    """
    return zappi.zappi_data


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
