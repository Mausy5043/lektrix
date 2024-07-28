#!/usr/bin/env python3

"""Daemon to periodically interogate the smart electricity meter to fetch energy mains data.

Store the data in a SQLite3 database.
"""

import argparse
import logging
import logging.handlers
import os
import shutil
import sys
import syslog
import time
import traceback

import mausy5043_common.funfile as mf
import mausy5043_common.libsqlite3 as m3

import constants
import libkamstrup as kl
import GracefulKiller as gk

logging.basicConfig(
    level=logging.INFO,
    format="%(module)s.%(funcName)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.handlers.SysLogHandler(
            address="/dev/log", facility=logging.handlers.SysLogHandler.LOG_DAEMON
        )
    ],
)
LOGGER: logging.Logger = logging.getLogger(__name__)

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
    killer = gk.GracefulKiller()
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
                LOGGER.critical(
                    "Unexpected error while trying to do some work!"
                )
                LOGGER.error(traceback.format_exc())
                raise
            if not succes:
                set_led("mains", "orange")
                LOGGER.warning("Getting telegram failed")
            # check if we already need to report the result data
            if time.time() > rprt_time:
                LOGGER.debug("Reporting")
                LOGGER.debug(f"Result   : {API_KL.list_data}")
                # resample to 15m entries
                data, API_KL.list_data = API_KL.compact_data(API_KL.list_data)
                try:
                    for element in data:
                        # LOGGER.debug(f"{element}") # is already logged by sql_db.queue()
                        sql_db.queue(element)
                except Exception:  # noqa
                    set_led("mains", "red")
                    LOGGER.critical(
                        "Unexpected error while trying to queue the data"
                    )
                    LOGGER.error(traceback.format_exc())
                    raise  # may be changed to pass if errors can be corrected.
                try:
                    sql_db.insert(method="replace")
                except Exception:  # noqa
                    set_led("mains", "red")
                    LOGGER.critical(
                        "Unexpected error while trying to commit the data to the database"
                    )
                    LOGGER.error(traceback.format_exc())
                    raise  # may be changed to pass if errors can be corrected.

            # electricity meter determines the tempo, so no need to wait.
            pause_interval = 0.0  # faux variable

            next_time = (
                pause_interval + time.time()
            )  # gives the actual time when the next loop should start
            # determine moment of next report
            rprt_time = time.time() + (report_interval - (time.time() % report_interval))
            LOGGER.debug(f"Spent {time.time() - start_time:.1f}s getting data")
            LOGGER.debug(f"Report in {rprt_time - time.time():.0f}s")
            LOGGER.debug("................................")
        else:
            time.sleep(1.0)  # 1s resolution is enough


def set_led(dev, colour):
    LOGGER.debug(f"{dev} is {colour}")

    in_dirfile = f"{APPROOT}/www/{colour}.png"
    out_dirfile = f'{constants.TREND["website"]}/{dev}.png'
    shutil.copy(f"{in_dirfile}", out_dirfile)


if __name__ == "__main__":
    # initialise logging
    syslog.openlog(ident=f'{MYAPP}.{MYID.split(".")[0]}', facility=syslog.LOG_LOCAL0)

    if OPTION.debug:
        DEBUG = True
        print(OPTION)
        if len(LOGGER.handlers) == 0:
            LOGGER.addHandler(logging.StreamHandler(sys.stdout))
        LOGGER.level = logging.DEBUG
        LOGGER.debug("Debugging on.")
        LOGGER.debug("Debug-mode started.")
        print("Use <Ctrl>+C to stop.")

    # OPTION.start only executes this next line, we don't need to test for it.
    main()

    LOGGER.debug("And it's goodnight from him")
