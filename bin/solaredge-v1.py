#!/usr/bin/env python3

# lektrix - solaredge-v1
# Copyright (C) 2025  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Script to call the SolarEdge API, using the module py-solaredge, to fetch energy production data.

Store the data in a SQLite3 database.
"""

import argparse
import configparser
import datetime as dt
import json
import logging.handlers
import os
import platform
import shutil
import sys
import time
import traceback

import constants as cs
import GracefulKiller as gk  # type: ignore[import-untyped]
import mausy5043_common.libsqlite3 as m3
from solaredge.api.client import Client  # type: ignore[import-untyped]

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
parser = argparse.ArgumentParser(description="Execute the solaredge daemon.")
parser_group = parser.add_mutually_exclusive_group(required=True)
_ = parser_group.add_argument(
    "--single",
    action="store_true",
    help="start the daemon as a service"
)
_ = parser_group.add_argument(
    "--debug",
    action="store_true",
    help="start the daemon in debugging mode"
)
OPTION = parser.parse_args()
# fmt: on

# constants
DEBUG = False
HERE: list[str] = os.path.realpath(__file__).split("/")
# runlist id :
MYID: str = HERE[-1]
# app_name :
MYAPP: str = HERE[-3]
MYROOT: str = "/".join(HERE[0:-3])
APPROOT: str = "/".join(HERE[0:-2])
# host_name :
NODE: str = os.uname()[1]


def main() -> None:
    """Execute main loop until killed."""
    LOGGER.info(f"{MYAPP} running on Python {sys.version}")
    debug_loop = False
    meas_ready = False
    set_led("solar", "orange")
    killer = gk.GracefulKiller()
    iniconf = configparser.ConfigParser()
    # read api_key from the file ~/.config/solaredge/account.ini
    _ = iniconf.read(cs.SOLAREDGE["config"])
    api_key: str = iniconf.get("account", "api_key")
    sol = Client()
    sol.set_api_key(api_key)
    sites = sol.sites.get_sites()
    site_id = sites["sites"]["site"][0]["id"]
    start_dt: dt.datetime = dt.datetime.today() - dt.timedelta(days=1)
    LOGGER.debug(
        json.dumps(sol.sites.get_site_details(site_id=site_id), indent=2, sort_keys=True)
    )

    sql_db = m3.SqlDatabase(
        database=cs.SOLAREDGE["database"],
        table=cs.SOLAREDGE["sql_table"],
        insert=cs.SOLAREDGE["sql_command"],
        debug=DEBUG,
    )
    start_dt = dt.datetime.strptime(sql_db.latest_datapoint(), cs.DT_FORMAT)

    report_interval = int(cs.SOLAREDGE["report_interval"])
    sample_interval: float = report_interval / int(cs.SOLAREDGE["samplespercycle"])
    pause_interval: float = 0.0
    next_time: float = cs.this_quarter_hour_end(cs.local_now(), cs.QUARTER_FINAL)
    lookback_hours = 24
    lookahead_days = 1
    set_led("solar", "orange")
    while not killer.kill_now and not debug_loop and not meas_ready:  # pylint: disable=too-many-nested-blocks
        # wait for the next whole quarter-hour interval
        if cs.local_now() > next_time:
            start_time: float = cs.local_now()
            if start_dt > dt.datetime.today():
                LOGGER.debug(f"Can't query {start_dt.strftime('%Y-%m-%d')} in the future.")
                start_dt = dt.datetime.today()
                LOGGER.debug(f"Will update data for  {start_dt.strftime('%Y-%m-%d')}.")
            try:
                data: list[dict] = do_work(
                    client=sol, site_id=site_id, start_dt=start_dt, lookback=lookback_hours
                )
                set_led("solar", "green")
                # only during the first loop do we need to lookback further
                lookback_hours = 2
            except Exception:  # noqa  # pylint: disable=W0718
                set_led("solar", "red")
                LOGGER.critical("Unexpected error while trying to do some work!")
                LOGGER.critical(traceback.format_exc())
                raise

            # Not pushing data to the database when debugging.
            LOGGER.debug(f"Data to add (first) : {data[0]}")
            LOGGER.debug(f"            (last)  : {data[-1]}")
            if data:
                try:
                    for element in data:
                        # also add data for the running quarter
                        if element["sample_epoch"] < (cs.local_now() + 15 * 60):
                            sql_db.queue(element)
                except Exception:  # noqa  # pylint: disable=W0718
                    set_led("solar", "red")
                    LOGGER.warning("Unexpected error while trying to queue the data")
                    LOGGER.warning(traceback.format_exc())
                    raise  # may be changed to pass if errors can be corrected.
                try:
                    sql_db.insert(method="replace")
                except Exception:  # noqa  # pylint: disable=W0718
                    set_led("solar", "red")
                    LOGGER.warning(
                        "Unexpected error while trying to commit the data to the database"
                    )
                    LOGGER.warning(traceback.format_exc())
                    raise  # may be changed to pass if errors can be corrected.

            # fmt: off
            pause_interval = (
                sample_interval
                - (cs.local_now() - start_time)  # time spent in this loop           eg. (40-3) = 37s
                - (start_time % sample_interval)  # number of seconds to next loop    eg. 3 % 60 = 3s
            )
            # fmt: on
            # allow the inverter to update the data on the server.
            pause_interval += cs.SOLAREDGE["delay"]
            next_time = cs.this_quarter_hour_end(
                pause_interval + cs.local_now(), cs.QUARTER_FINAL
            )  # gives the actual time when the next loop should start
            # pylint: disable-next=W0105
            """Example calculation:
            sample_interval = 60s   # target duration one loop
            time.time() = 40    # actual current time
            start_time = 3      # actual current time when the loop was started

            sample_interval - ( time.time() - start_time ) - ( start_time % sample_interval )
                60      - (     40      -     3      ) - (     3      %    60       )
                60      -             37               -            3
             = 20 s waiting time

            Example 2:
                60      - (     181     -     122      ) - (     122      %    60       )
                60      -             59                -            2
             = 3 seconds behind (no waiting)
            """

            new_start_dt: dt.datetime = dt.datetime.strptime(
                sql_db.latest_datapoint(), cs.DT_FORMAT
            )
            if new_start_dt <= start_dt:
                # there is a hole in the data
                LOGGER.warning(
                    f"Found a hole in the data starting at {
                        new_start_dt.strftime('%Y-%m-%d %H:%M:%S')
                    }."
                )
                dati: dt.datetime = new_start_dt + dt.timedelta(days=lookahead_days)
                if dati > dt.datetime.today():
                    LOGGER.debug(f"Can't jump to {dati.strftime('%Y-%m-%d')} in the future.")
                    dati = dt.datetime.today()
                start_dt = dati
                LOGGER.warning(
                    f"Attempting to cross it at {start_dt.strftime('%Y-%m-%d %H:%M:%S')}."
                )
                # if we don't cross the gap then next time check more days ahead
                lookahead_days += 1
                if DEBUG:
                    pause_interval = 10
            else:
                start_dt = new_start_dt
                lookahead_days = 1
                meas_ready = bool(OPTION.single)  # measurement is ready
                LOGGER.info(f"Data updated up to {start_dt.strftime('%Y-%m-%d %H:%M:%S')}.")
            if pause_interval > 0:
                LOGGER.debug(f"Waiting  : {pause_interval:.1f}s")
                LOGGER.debug("................................")
            else:
                LOGGER.debug(f"Behind   : {pause_interval:.1f}s")
                LOGGER.debug("................................")
        else:
            time.sleep(1.0)  # 1s resolution is enough
        debug_loop = bool(OPTION.debug)


def do_work(client, site_id, start_dt=None, lookback=4) -> list:
    """Extract the data from the dict(s)."""
    if start_dt is None:
        start_dt = dt.datetime.now()

    # request 4 hours back and 1 day ahead
    back_dt = dt.datetime.strftime(start_dt - dt.timedelta(hours=lookback), cs.D_FORMAT)
    end_dt = dt.datetime.strftime(start_dt + dt.timedelta(days=1), cs.D_FORMAT)
    data_list: list[dict] = []
    result_list: list[dict] = []

    try:
        sol_energy = client.sites.get_energy(
            site_id=site_id,
            startDate=back_dt,
            endDate=end_dt,
            timeUnit="QUARTER_OF_AN_HOUR",
        )
        data_list = sol_energy["energy"]["values"]
        if DEBUG:
            for item in data_list:
                LOGGER.debug(f"    : {item}")
    except (json.decoder.JSONDecodeError, KeyError):
        LOGGER.warning("Request returned no usable data.")
        LOGGER.warning("Maybe next time...")
    except Exception:  # noqa  # pylint: disable=W0718
        LOGGER.error("Unhandled error occured.")
        LOGGER.error(traceback.format_exc())
        raise

    # data_list looks like this:
    # [
    # {'date': '2024-11-26 08:00:00', 'value': 38.0},
    # {'date': '2024-11-26 09:00:00', 'value': 191.0},
    # {'date': '2024-11-26 10:00:00', 'value': 390.0},
    # {'date': '2024-11-26 11:00:00', 'value': 1059.0},
    # {'date': '2024-11-26 12:00:00', 'value': 753.0},
    # {'date': '2024-11-26 13:00:00', 'value': 382.0},
    # {'date': '2024-11-26 14:00:00', 'value': 239.0},
    # {'date': '2024-11-26 15:00:00', 'value': 69.0},
    # {'date': '2024-11-26 16:00:00', 'value': 0.0},
    # {'date': '2024-11-26 17:00:00', 'value': None}
    # ]

    if data_list:
        for element in data_list:
            result_dict: dict = {}
            date_time: str = element["date"]
            try:
                # element["value"] may be None; return 0.0 in that case
                energy: float = element["value"] or 0.0
            except KeyError:
                energy = 0.0
            result_dict["sample_time"] = date_time
            result_dict["sample_epoch"] = int(
                dt.datetime.strptime(date_time, cs.DT_FORMAT).replace(tzinfo=dt.UTC).timestamp()
            )
            result_dict["site_id"] = site_id
            result_dict["solar"] = int(energy)
            LOGGER.debug(f"    : {date_time} = {energy}")
            result_list.append(result_dict)
    return result_list


def set_led(dev, colour) -> None:
    LOGGER.debug(f"{dev} is {colour}")

    in_dirfile: str = f"{APPROOT}/www/{colour}.png"
    out_dirfile: str = f'{cs.TREND["website"]}/{dev}.png'
    shutil.copy(f"{in_dirfile}", out_dirfile)


if __name__ == "__main__":
    if OPTION.debug:
        DEBUG = True
        print(OPTION)
        if len(LOGGER.handlers) == 0:
            LOGGER.addHandler(logging.StreamHandler(sys.stdout))
        LOGGER.setLevel(logging.DEBUG)
        LOGGER.debug("Debug-mode started.")
        print("Use <Ctrl>+C to stop.")

    # OPTION.start only executes this next line, we don't need to test for it.
    main()

    print("And it's goodnight from him (solaredge-v1)")
