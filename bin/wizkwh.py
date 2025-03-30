#!/usr/bin/env python3

# lektrix - wizkwh
# Copyright (C) 2025  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

"""Daemon to periodically interogate the Home Wizard kWh meters to fetch energy usage data.

Store the data in a SQLite3 database.
"""

import argparse
import logging.handlers
import os
import shutil
import sys
import syslog
import time
import traceback

import constants as cs
import GracefulKiller as gk  # type: ignore[import-untyped]
import libwizkwh as kwh
import mausy5043_common.libsqlite3 as m3

logging.basicConfig(
    level=logging.INFO,
    format="%(module)s.%(funcName)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.handlers.SysLogHandler(
            address="/dev/log",
            facility=logging.handlers.SysLogHandler.LOG_DAEMON,
        )
    ],
)
LOGGER: logging.Logger = logging.getLogger(__name__)

# fmt: off
parser = argparse.ArgumentParser(description="Execute the home wizard P1 daemon.")
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
# example HERE = ['', 'home', 'pi', 'lektrix', 'bin', 'wizkwh.py']
MYID = HERE[-1]  # wizkwh.py
MYAPP = HERE[-3]  # lektrix
MYROOT = "/".join(HERE[0:-3])  # /home/pi
APPROOT = "/".join(HERE[0:-2])  # /home/pi/lektrix
NODE = os.uname()[1]  # rbelec
# fmt: on


def main() -> None:
    """Execute main loop until killed."""
    LOGGER.info(f"Running on Python {sys.version}")
    set_led("ev", "orange")
    set_led("pv", "orange")
    killer = gk.GracefulKiller()
    API_KWH = kwh.WizkWh(debug=DEBUG)
    sql_db = m3.SqlDatabase(
        database=cs.WIZ_KWH["database"],
        table=cs.WIZ_KWH["sql_table"],
        insert=cs.WIZ_KWH["sql_command"],
        debug=DEBUG,
    )

    report_interval = int(cs.WIZ_KWH["report_interval"])
    sample_interval = report_interval / int(cs.WIZ_KWH["samplespercycle"])

    next_time = time.time()
    rprt_time = time.time() + (report_interval - (time.time() % report_interval))
    while not killer.kill_now:
        if time.time() > next_time:
            start_time = time.time()
            try:
                LOGGER.debug("\n...requesting telegram")
                API_KWH.get_telegram()
                set_led("p1", "green")
                set_led("ev", "green")
                set_led("pv", "green")
            except Exception:  # noqa
                set_led("p1", "red")
                set_led("ev", "red")
                set_led("pv", "red")
                LOGGER.critical("Unexpected error while trying to do some work!")
                LOGGER.error(traceback.format_exc())
                raise
            # check if we already need to report the result data
            if time.time() > rprt_time:
                LOGGER.debug("\n...reporting")
                LOGGER.debug(f"Result   : {API_KWH.list_data}")
                # resample to 15m entries
                data, API_KWH.list_data = API_KWH.compact_data(API_KWH.list_data)
                try:
                    LOGGER.debug("\n...queueing")
                    for element in data:
                        LOGGER.debug(f"{element}")  # is already logged by sql_db.queue()
                        sql_db.queue(element)
                except Exception:  # noqa
                    set_led("p1", "red")
                    set_led("ev", "red")
                    set_led("pv", "red")
                    LOGGER.critical("Unexpected error while trying to queue the data")
                    LOGGER.error(traceback.format_exc())
                    raise  # may be changed to pass if errors can be corrected.
                try:
                    LOGGER.debug("\n...inserting data")
                    sql_db.insert(method="replace")
                except Exception:  # noqa
                    set_led("p1", "red")
                    set_led("ev", "red")
                    set_led("pv", "red")
                    LOGGER.critical(
                        "Unexpected error while trying to commit the data to the database"
                    )
                    LOGGER.error(traceback.format_exc())
                    raise  # may be changed to pass if errors can be corrected.

            # determine moment of next report
            next_time = sample_interval + start_time - (start_time % sample_interval)
            rprt_time = time.time() + (report_interval - (time.time() % report_interval))
            LOGGER.debug(f"Spent          {time.time() - start_time:.1f}s getting data")
            LOGGER.debug(f"Report in      {rprt_time - time.time():.0f}s")
            LOGGER.debug(f"Next sample in {next_time - time.time():.0f}s")
            LOGGER.debug("................................")
        else:
            time.sleep(1.0)  # 1s resolution is enough


def set_led(dev, colour) -> None:
    LOGGER.debug(f"{dev} is {colour}")

    in_dirfile = f"{APPROOT}/www/{colour}.png"
    out_dirfile = f'{cs.TREND["website"]}/{dev}.png'
    shutil.copy(f"{in_dirfile}", out_dirfile)


if __name__ == "__main__":
    # initialise logging
    syslog.openlog(
        ident=f'{MYAPP}.{MYID.split(".")[0]}',
        facility=syslog.LOG_LOCAL0,
    )

    if OPTION.debug:
        DEBUG = True
        print(OPTION)
        if len(LOGGER.handlers) == 0:
            LOGGER.addHandler(logging.StreamHandler(sys.stdout))
        LOGGER.level = logging.DEBUG
        LOGGER.debug("Debug-mode started.")
        print("Use <Ctrl>+C to stop.")

    # OPTION.start only executes this next line, we don't need to test for it.
    main()

    LOGGER.info("And it's goodnight from him")
