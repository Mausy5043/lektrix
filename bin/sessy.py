#!/usr/bin/env python3

# lektrix - sessy
# Copyright (C) 2025  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Daemon to periodically interogate the Sessy home battery to fetch SoC info.

Store the data in a SQLite3 database.
"""

import argparse
import logging.handlers
import datetime as dt
import os
import platform
import shutil
import sys
import time
import traceback

import constants as cs
import GracefulKiller as gk  # type: ignore[import-untyped]
import libsessy as bat
import mausy5043_common.libsqlite3 as m3

# Declare the handler type for mypy
handler: logging.Handler
sys_log = "/dev/log"  # default for Linux / Debian
if platform.system() == "Darwin":
    sys_log = "/var/run/syslog"  # default for macOS
# configure the handler
if os.path.exists(sys_log):
    handler = logging.handlers.SysLogHandler(
        address=sys_log,
        facility=logging.handlers.SysLogHandler.LOG_DAEMON,
    )
else:
    # fallback to stdout for podman/docker or if syslog is not available
    handler = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO,
    format="%(module)s.%(funcName)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[handler],
)
LOGGER: logging.Logger = logging.getLogger(__name__)

# fmt: off
parser = argparse.ArgumentParser(description="Execute the home wizard P1 daemon.")
parser_group = parser.add_mutually_exclusive_group(required=True)
parser_group.add_argument("--single",
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
# example HERE = ['', 'home', 'pi', 'lektrix', 'bin', 'sessy.py']
MYID = HERE[-1]  # sessy.py
MYAPP = HERE[-3]  # lektrix
MYROOT = "/".join(HERE[0:-3])  # /home/pi
APPROOT = "/".join(HERE[0:-2])  # /home/pi/lektrix
NODE = os.uname()[1]  # rbelec
# fmt: on


def main() -> None:
    """Execute main loop until killed."""
    LOGGER.info(f"Running on Python {sys.version}")
    set_led("bat", "orange")
    killer = gk.GracefulKiller()
    API_SES = bat.SesBat(debug=DEBUG)
    sql_db = m3.SqlDatabase(
        database=cs.BATTERY["database"],
        table=cs.BATTERY["sql_table"],
        insert=cs.BATTERY["sql_command"],
        debug=DEBUG,
    )
    meas_ready = False
    report_interval = int(cs.BATTERY["report_interval"])
    sample_interval = report_interval / int(cs.BATTERY["samplespercycle"])

    # next_time = time.time()
    next_time: float = next_quarter_hour(local_now())
    rprt_time = local_now() + (report_interval - (local_now() % report_interval))
    while not killer.kill_now and not meas_ready:
        if local_now() > next_time:
            start_time = local_now()
            try:
                LOGGER.debug("\n...requesting telegram")
                API_SES.get_telegram()
                set_led("bat", "green")
            except Exception:  # noqa
                set_led("bat", "red")
                LOGGER.critical("Unexpected error while trying to do some work!")
                LOGGER.error(traceback.format_exc())
                raise
            # check if we already need to report the result data
            # if local_now() > rprt_time:
            LOGGER.debug("\n...reporting")
            LOGGER.debug(f"Result   : {API_SES.list_data}")
            # resample to 15m entries
            data, API_SES.list_data = API_SES.compact_data(API_SES.list_data)
            try:
                LOGGER.debug("\n...queueing")
                for element in data:
                    LOGGER.debug(f"{element}")  # is already logged by sql_db.queue()
                    sql_db.queue(element)
            except Exception:  # noqa
                set_led("bat", "red")
                LOGGER.critical("Unexpected error while trying to queue the data")
                LOGGER.error(traceback.format_exc())
                raise  # may be changed to pass if errors can be corrected.
            try:
                LOGGER.debug("\n...inserting data")
                sql_db.insert(method="replace")
            except Exception:  # noqa
                set_led("bat", "red")
                LOGGER.critical(
                    "Unexpected error while trying to commit the data to the database"
                )
                LOGGER.error(traceback.format_exc())
                raise  # may be changed to pass if errors can be corrected.
            # # endif
            LOGGER.info("sessy measurement cycle complete.")
            meas_ready = bool(OPTION.single)  # measurement is ready
            # determine moment of next report
            next_time = sample_interval + start_time - (start_time % sample_interval)
            rprt_time = local_now() + (report_interval - (local_now() % report_interval))
            LOGGER.debug(f"Spent          {local_now() - start_time:.1f}s getting data")
            LOGGER.debug(f"Report in      {rprt_time - local_now():.0f}s")
            LOGGER.debug(f"Next sample in {next_time - local_now():.0f}s")
            LOGGER.debug("................................")
        else:
            time.sleep(1.0)  # 1s resolution is enough


def local_now() -> float:
    """Return the current timestamp in UTC."""
    return dt.datetime.today().replace(tzinfo=dt.UTC).timestamp()


def next_quarter_hour(ts: float) -> float:
    """Return the timestamp of the next quarter-hour."""
    next_ts = (-ts) % (15 * 60)
    return next_ts + ts

def set_led(dev, colour) -> None:
    LOGGER.debug(f"{dev} is {colour}")

    in_dirfile = f"{APPROOT}/www/{colour}.png"
    out_dirfile = f'{cs.TREND["website"]}/{dev}.png'
    shutil.copy(f"{in_dirfile}", out_dirfile)


if __name__ == "__main__":
    if OPTION.debug:
        print(OPTION)
        if len(LOGGER.handlers) == 0:
            LOGGER.addHandler(logging.StreamHandler(sys.stdout))
        LOGGER.setLevel(logging.DEBUG)
        DEBUG = True
        LOGGER.debug("DEBUG-mode started")
        print("Use <Ctrl>+C to stop.")

    # OPTION.start only executes this next line, we don't need to test for it.
    main()

    LOGGER.info("And it's goodnight from him (sessy)")
