#!/usr/bin/env python3

# lektrix
# Copyright (C) 2024  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

"""Daemon to periodically call the SolarEdge API, using the local module libsolaredge,
   to fetch energy production data.

Store the data in a SQLite3 database.
"""

import argparse
import configparser
import datetime as dt
import os
import shutil
import syslog
import time
import traceback

import constants
import GracefulKiller as gk
import libsolaredge as sl
import mausy5043_common.funfile as mf
import mausy5043_common.libsqlite3 as m3

# fmt: off
parser = argparse.ArgumentParser(description="Execute the solaredge daemon.")
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

# example values:
# HERE: ['', 'home', 'pi', 'lektrix', 'bin', 'solaredge.py']
# MYID: 'solaredge.py
# MYAPP: lektrix
# MYROOT: /home/pi
# NODE: rbelec

API_SE = sl.Solaredge("000000")


def main() -> None:
    """Execute main loop until killed."""
    global API_SE  # pylint: disable=W0603
    set_led("solar", "orange")
    killer = gk.GracefulKiller()
    iniconf = configparser.ConfigParser()
    # read api_key from the file ~/.config/solaredge/account.ini
    iniconf.read(f"{os.environ['HOME']}/.config/solaredge/account.ini")
    api_key: str = iniconf.get("account", "api_key")
    API_SE = sl.Solaredge(api_key)

    sql_db = m3.SqlDatabase(
        database=constants.SOLAREDGE["database"],
        table="production",
        insert=constants.SOLAREDGE["sql_command"],
        debug=DEBUG,
    )

    report_interval = int(constants.SOLAREDGE["report_interval"])
    sample_interval: float = report_interval / int(constants.SOLAREDGE["samplespercycle"])

    site_list: list[str] = []
    pause_interval: float = 0.2
    next_time: float = pause_interval + local_now()
    start_dt: dt.datetime = dt.datetime.strptime(sql_db.latest_datapoint(), constants.DT_FORMAT)
    lookback_hours = 24
    lookahead_days = 1
    while not killer.kill_now:  # pylint: disable=too-many-nested-blocks
        if local_now() > next_time:
            start_time: float = local_now()

            if not site_list:
                try:
                    site_list = API_SE.get_list()["sites"]["site"]
                except Exception:  # noqa  # pylint: disable=W0718
                    set_led("solar", "orange")
                    mf.syslog_trace("Error connecting to SolarEdge", syslog.LOG_CRIT, DEBUG)
                    mf.syslog_trace(traceback.format_exc(), syslog.LOG_CRIT, DEBUG)
                    site_list = []

            if site_list:
                if start_dt > dt.datetime.today():
                    mf.syslog_trace(
                        f"Can't query {start_dt.strftime('%Y-%m-%d')} in the future.",
                        False,
                        DEBUG,
                    )
                    start_dt = dt.datetime.today()
                    mf.syslog_trace(
                        f"Will update data for  {start_dt.strftime('%Y-%m-%d')}.",
                        False,
                        DEBUG,
                    )
                try:
                    data: list[dict] = do_work(
                        site_list, start_dt=start_dt, lookback=lookback_hours
                    )
                    set_led("solar", "green")
                    # only during the first loop do we need to lookback further
                    lookback_hours = 2
                except Exception:  # noqa  # pylint: disable=W0718
                    set_led("solar", "red")
                    mf.syslog_trace(
                        "Unexpected error while trying to do some work!",
                        syslog.LOG_CRIT,
                        DEBUG,
                    )
                    mf.syslog_trace(traceback.format_exc(), syslog.LOG_CRIT, DEBUG)
                    raise
                if data:
                    try:
                        mf.syslog_trace(f"Data to add (first) : {data[0]}", False, DEBUG)
                        mf.syslog_trace(f"            (last)  : {data[-1]}", False, DEBUG)
                        for element in data:
                            # also add data for the running quarter
                            if element["sample_epoch"] < (local_now() + 15 * 60):
                                sql_db.queue(element)
                    except Exception:  # noqa  # pylint: disable=W0718
                        set_led("solar", "red")
                        mf.syslog_trace(
                            "Unexpected error while trying to queue the data",
                            syslog.LOG_ALERT,
                            DEBUG,
                        )
                        mf.syslog_trace(traceback.format_exc(), syslog.LOG_ALERT, DEBUG)
                        raise  # may be changed to pass if errors can be corrected.
                    try:
                        sql_db.insert(method="replace")
                    except Exception:  # noqa  # pylint: disable=W0718
                        set_led("solar", "red")
                        mf.syslog_trace(
                            "Unexpected error while trying to commit the data to the database",
                            syslog.LOG_ALERT,
                            DEBUG,
                        )
                        mf.syslog_trace(traceback.format_exc(), syslog.LOG_ALERT, DEBUG)
                        raise  # may be changed to pass if errors can be corrected.

            pause_interval = (
                sample_interval
                - (local_now() - start_time)  # time spent in this loop           eg. (40-3) = 37s
                - (
                    start_time % sample_interval
                )  # number of seconds to next loop    eg. 3 % 60 = 3s
            )
            pause_interval += constants.SOLAREDGE[
                "delay"
            ]  # allow the inverter to update the data on the server.
            next_time = (
                pause_interval + local_now()
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
                sql_db.latest_datapoint(), constants.DT_FORMAT
            )
            if new_start_dt <= start_dt:
                # there is a hole in the data
                mf.syslog_trace(
                    f"Found a hole in the data starting at "
                    f"{new_start_dt.strftime('%Y-%m-%d %H:%M:%S')}.",
                    syslog.LOG_WARNING,
                    DEBUG,
                )
                dati: dt.datetime = new_start_dt + dt.timedelta(days=lookahead_days)
                if dati > dt.datetime.today():
                    mf.syslog_trace(
                        f"Can't jump to {dati.strftime('%Y-%m-%d')} in the future.",
                        syslog.LOG_WARNING,
                        DEBUG,
                    )
                    dati = dt.datetime.today()
                start_dt = dati
                mf.syslog_trace(
                    f"Attempting to cross it at {start_dt.strftime('%Y-%m-%d %H:%M:%S')}.",
                    syslog.LOG_WARNING,
                    DEBUG,
                )
                # if we don't cross the gap then next time check more days ahead
                lookahead_days += 1
                if DEBUG:
                    pause_interval = 10
            else:
                start_dt = new_start_dt
                lookahead_days = 1

            if pause_interval > 0:
                mf.syslog_trace(
                    f"Waiting  : {pause_interval:.1f}s",
                    False,
                    DEBUG,
                )
                mf.syslog_trace("................................", False, DEBUG)
            else:
                mf.syslog_trace(
                    f"Behind   : {pause_interval:.1f}s",
                    False,
                    DEBUG,
                )
                mf.syslog_trace("................................", False, DEBUG)
        else:
            time.sleep(1.0)  # 1s resolution is enough


def do_work(site_list, start_dt=dt.datetime.today(), lookback=4) -> list:
    """Extract the data from the dict(s)."""

    # TODO: This function should be implemented in libsolaredge

    # request 4 hours back and 1 day ahead
    back_dt: dt.datetime = start_dt - dt.timedelta(hours=lookback)
    start_dt += dt.timedelta(days=1)
    # result_dict = constants.SOLAREDGE['template']
    data_list: list[dict] = []
    result_list: list[dict] = []

    for site in site_list:
        site_id: str = site["id"]
        try:
            data_list = API_SE.get_energy_details(
                site_id,
                dt.datetime.strftime(back_dt, constants.DT_FORMAT),
                dt.datetime.strftime(start_dt, constants.DT_FORMAT),
                time_unit="QUARTER_OF_AN_HOUR",
            )["energyDetails"]["meters"][0]["values"]
        except Exception:  # noqa  # pylint: disable=W0718
            mf.syslog_trace("Request was unsuccesful.", syslog.LOG_WARNING, DEBUG)
            mf.syslog_trace(traceback.format_exc(), syslog.LOG_WARNING, DEBUG)
            mf.syslog_trace("Maybe next time...", syslog.LOG_WARNING, DEBUG)

        # data_list looks like this:
        # [{'date': '2022-04-30 05:15:00'},
        #  {'date': '2022-04-30 05:30:00'},
        #  {'date': '2022-04-30 05:45:00'},
        #  {'date': '2022-04-30 06:00:00'},
        #  {'date': '2022-04-30 06:15:00', 'value': 0.0},
        #  {'date': '2022-04-30 06:30:00', 'value': 2.0},
        #  {'date': '2022-04-30 06:45:00', 'value': 10.0}
        #  ...
        # ]

        if data_list:
            for element in data_list:
                result_dict: dict = {}
                date_time: str = element["date"]
                try:
                    energy: float = element["value"]
                except KeyError:
                    energy = 0.0

                result_dict["sample_time"] = date_time
                result_dict["sample_epoch"] = int(
                    dt.datetime.strptime(date_time, constants.DT_FORMAT)
                    .replace(tzinfo=dt.timezone.utc)
                    .timestamp()
                )
                result_dict["site_id"] = site_id
                result_dict["energy"] = int(energy)
                mf.syslog_trace(f"    : {date_time} = {energy}", False, DEBUG)
                result_list.append(result_dict)
    return result_list


def local_now() -> float:
    return dt.datetime.today().replace(tzinfo=dt.timezone.utc).timestamp()


def set_led(dev, colour) -> None:
    mf.syslog_trace(f"{dev} is {colour}", False, DEBUG)

    in_dirfile: str = f"{APPROOT}/www/{colour}.png"
    out_dirfile: str = f'{constants.TREND["website"]}/{dev}.png'
    shutil.copy(f"{in_dirfile}", out_dirfile)


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
