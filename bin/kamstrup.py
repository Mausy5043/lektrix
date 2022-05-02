#!/usr/bin/env python3
"""Daemon to periodically interogate the smart electricity meter to fetch energy mains data.

Store the data in a SQLite3 database.
"""
import argparse
import configparser
import datetime as dt
import os
import syslog
import time
import traceback

import mausy5043funcs.fileops3 as mf
import mausy5043libs.libsignals3 as ml
import mausy5043libs.libsqlite3 as m3

import constants
import libkamstrup as kl


parser = argparse.ArgumentParser(description="Execute the kamstrup daemon.")
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

API_KL = None
# example values:
# HERE: ['', 'home', 'pi', 'lektrix', 'bin', 'kamstrup.py']
# MYID: kamstrup.py
# MYAPP: lektrix
# MYROOT: /home/pi
# NODE: rbelec


def main():
    """Execute main loop until killed."""
    global API_KL
    killer = ml.GracefulKiller()
    API_KL = kl.Kamstrup(DEBUG)

    sql_db = m3.SqlDatabase(database=constants.KAMSTRUP['database'],
                            table='mains', insert=constants.KAMSTRUP['sql_command'],
                            debug=DEBUG
                            )

    report_time = int(constants.KAMSTRUP['report_time'])
    sample_time = report_time / int(constants.KAMSTRUP['samplespercycle'])

    pause_time = 0
    next_time = time.time() + (sample_time - (time.time() % sample_time))
    rprt_time = time.time() + (report_time - (time.time() % report_time))
    data = None     # FIXME: for testing
    while not killer.kill_now:
        if time.time() > next_time:
            start_time = time.time()
            try:
                succes = API_KL.get_telegram()
            except Exception:  # noqa
                mf.syslog_trace("Unexpected error while trying to do some work!", syslog.LOG_CRIT, DEBUG)
                mf.syslog_trace(traceback.format_exc(), syslog.LOG_CRIT, DEBUG)
                raise
            if not succes:
                mf.syslog_trace("Getting telegram failed", syslog.LOG_WARNING, DEBUG)
            if time.time() > rprt_time:
                mf.syslog_trace("Reporting", False, DEBUG)
                if DEBUG:
                    mf.syslog_trace(f"Result   : {API_KL.list_data}", False, DEBUG)
                rprt_time = start_time + report_time
                #
                API_KL.listdata = list() # FIXME: for testing
                rprt_time += constants.KAMSTRUP['delay']
            if data:
                try:
                    mf.syslog_trace(f"Data to add (first) : {data[0]}", False, DEBUG)
                    mf.syslog_trace(f"            (last)  : {data[-1]}", False, DEBUG)
                    for element in data:
                        sql_db.queue(element)
                except Exception:  # noqa
                    mf.syslog_trace("Unexpected error while trying to queue the data", syslog.LOG_ALERT, DEBUG)
                    mf.syslog_trace(traceback.format_exc(), syslog.LOG_ALERT, DEBUG)
                    raise  # may be changed to pass if errors can be corrected.
                try:
                    sql_db.insert()
                except Exception:  # noqa
                    mf.syslog_trace("Unexpected error while trying to commit the data to the database",
                                    syslog.LOG_ALERT, DEBUG)
                    mf.syslog_trace(traceback.format_exc(), syslog.LOG_ALERT, DEBUG)
                    raise  # may be changed to pass if errors can be corrected.

            # pause_time = (sample_time
            #               - (time.time() - start_time)  # time spent in this loop           eg. (40-3) = 37s
            #               - (start_time % sample_time)  # number of seconds to next loop    eg. 3 % 60 = 3s
            #               )
            # electricity meter determines the tempo, so no need to wait.
            pause_time = 0.
            next_time = pause_time + time.time()        # gives the actual time when the next loop should start
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
                mf.syslog_trace(f"Waiting  : {pause_time:.1f}s. Report in {rprt_time - time.time():.0f}s", False, DEBUG)
                mf.syslog_trace("................................", False, DEBUG)
            else:
                mf.syslog_trace(f"Behind   : {pause_time:.1f}s. Report in {rprt_time - time.time():.0f}s", False, DEBUG)
                mf.syslog_trace("................................", False, DEBUG)
        else:
            time.sleep(1.0)  # 1s resolution is enough


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
