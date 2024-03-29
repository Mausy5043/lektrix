#!/usr/bin/env python3

"""Daemon to periodically interogate the smart electricity meter to fetch energy mains data.

Store the data in a SQLite3 database.
"""

import argparse
import os
import shutil
import syslog
import time
import traceback

import mausy5043_common.funfile as mf
import mausy5043_common.libsignals as ml
import mausy5043_common.libsqlite3 as m3

import constants
import libkamstrup as kl

# fmt: off
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
# example HERE = ['', 'home', 'pi', 'lektrix', 'bin', 'kamstrup.py']
MYID = HERE[-1]  # kamstrup.py
MYAPP = HERE[-3]  # lektrix
MYROOT = "/".join(HERE[0:-3])  # /home/pi
APPROOT = "/".join(HERE[0:-2])  # /home/pi/lektrix
NODE = os.uname()[1]  # rbelec
# fmt: on


def main():
    """Execute main loop until killed."""
    set_led("mains", "orange")
    killer = ml.GracefulKiller()
    API_KL = kl.Kamstrup(DEBUG)

    sql_db = m3.SqlDatabase(
        database=constants.KAMSTRUP["database"],
        table=constants.KAMSTRUP["sql_table"],
        insert=constants.KAMSTRUP["sql_command"],
        debug=DEBUG,
    )

    report_interval = int(constants.KAMSTRUP["report_interval"])
    sample_interval = report_interval / int(constants.KAMSTRUP["samplespercycle"])

    next_time = time.time() + (sample_interval - (time.time() % sample_interval))
    rprt_time = time.time() + (report_interval - (time.time() % report_interval))
    while not killer.kill_now:
        if time.time() > next_time:
            start_time = time.time()
            try:
                succes = API_KL.get_telegram()
                set_led("mains", "green")
            except Exception:  # noqa
                set_led("mains", "red")
                mf.syslog_trace(
                    "Unexpected error while trying to do some work!",
                    syslog.LOG_CRIT,
                    DEBUG,
                )
                mf.syslog_trace(traceback.format_exc(), syslog.LOG_DEBUG, DEBUG)
                raise
            if not succes:
                set_led("mains", "orange")
                mf.syslog_trace("Getting telegram failed", syslog.LOG_WARNING, DEBUG)
            # check if we already need to report the result data
            if time.time() > rprt_time:
                mf.syslog_trace("Reporting", False, DEBUG)
                mf.syslog_trace(f"Result   : {API_KL.list_data}", False, DEBUG)
                # resample to 15m entries
                data, API_KL.list_data = API_KL.compact_data(API_KL.list_data)
                mf.syslog_trace(f"Remainder: {API_KL.list_data}", False, DEBUG)
                try:
                    mf.syslog_trace(f"Data to add (first) : {data[0]}", False, DEBUG)
                    mf.syslog_trace(f"            (last)  : {data[-1]}", False, DEBUG)
                    for element in data:
                        sql_db.queue(element)
                except Exception:  # noqa
                    set_led("mains", "red")
                    mf.syslog_trace(
                        "Unexpected error while trying to queue the data",
                        syslog.LOG_ALERT,
                        DEBUG,
                    )
                    mf.syslog_trace(traceback.format_exc(), syslog.LOG_ALERT, DEBUG)
                    raise  # may be changed to pass if errors can be corrected.
                try:
                    sql_db.insert(method="replace")
                except Exception:  # noqa
                    set_led("mains", "red")
                    mf.syslog_trace(
                        "Unexpected error while trying to commit the data to the database",
                        syslog.LOG_ALERT,
                        DEBUG,
                    )
                    mf.syslog_trace(traceback.format_exc(), syslog.LOG_ALERT, DEBUG)
                    raise  # may be changed to pass if errors can be corrected.

            # electricity meter determines the tempo, so no need to wait.
            pause_interval = 0.0  # faux variable

            next_time = (
                pause_interval + time.time()
            )  # gives the actual time when the next loop should start
            # determine moment of next report
            rprt_time = time.time() + (report_interval - (time.time() % report_interval))
            mf.syslog_trace(f"Spent {time.time() - start_time:.1f}s getting data", False, DEBUG)
            mf.syslog_trace(f"Report in {rprt_time - time.time():.0f}s", False, DEBUG)
            mf.syslog_trace("................................", False, DEBUG)
        else:
            time.sleep(1.0)  # 1s resolution is enough


def set_led(dev, colour):
    mf.syslog_trace(f"{dev} is {colour}", False, DEBUG)

    in_dirfile = f"{APPROOT}/www/{colour}.png"
    out_dirfile = f'{constants.TREND["website"]}/{dev}.png'
    shutil.copy(f"{in_dirfile}", out_dirfile)


if __name__ == "__main__":
    # initialise logging
    syslog.openlog(ident=f'{MYAPP}.{MYID.split(".")[0]}', facility=syslog.LOG_LOCAL0)

    if OPTION.debug:
        DEBUG = True
        print(OPTION)
        mf.syslog_trace("Debug-mode started.", syslog.LOG_DEBUG, DEBUG)
        print("Use <Ctrl>+C to stop.")

    # OPTION.start only executes this next line, we don't need to test for it.
    main()

    print("And it's goodnight from him")
