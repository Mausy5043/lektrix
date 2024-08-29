#!/usr/bin/env python3

"""Daemon to periodically call the Myenergy API to fetch energy production data.

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
import libmyenergi as zl
import mausy5043_common.funfile as mf
import mausy5043_common.libsqlite3 as m3

# fmt: off
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
# fmt: on

# constants
DEBUG = False
HERE = os.path.realpath(__file__).split("/")
# runlist id :
MYID = HERE[-1]
# app_name :
MYAPP = HERE[-3]
MYROOT = "/".join(HERE[0:-3])
APPROOT = "/".join(HERE[0:-2])
# host_name :
NODE = os.uname()[1]


# example values:
# HERE: ['', 'home', 'pi', 'lektrix', 'bin', 'myenergi.py']
# MYID: myenergi.py
# MYAPP: lektrix
# MYROOT: /home/pi
# NODE: rbelec


def main() -> None:
    """Execute main loop until killed."""
    set_led("ev", "orange")
    killer = gk.GracefulKiller()
    iniconf = configparser.ConfigParser()
    # read api_key from the file ~/.config/zappi/keys.ini
    api_keys_file = f"{os.environ['HOME']}/.config/zappi/keys.ini"
    iniconf.read(api_keys_file)
    API_ZP = zl.Myenergi(api_keys_file, DEBUG)

    sql_db = m3.SqlDatabase(
        database=constants.ZAPPI["database"],
        table="charger",
        insert=constants.ZAPPI["sql_command"],
        debug=DEBUG,
    )

    report_interval = int(constants.ZAPPI["report_interval"])
    sample_interval = report_interval / int(constants.ZAPPI["samplespercycle"])
    pause_interval: float = 0.01
    next_time: float = pause_interval + time.time()
    start_dt = sql_db.latest_datapoint()  # type: str
    lookahead_days = 1
    while not killer.kill_now:
        if time.time() > next_time:
            start_time: float = time.time()
            try:
                data: list = do_work(
                    API_ZP, start_dt=dt.datetime.strptime(start_dt, constants.DT_FORMAT)
                )  # noqa
                set_led("ev", "green")
            except ConnectionError:
                set_led("ev", "orange")
                data = None
                mf.syslog_trace(
                    "ConnectionError occured. Will try again later.",
                    syslog.LOG_WARNING,
                    DEBUG,
                )
            except Exception:  # noqa
                set_led("ev", "red")
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
                        sql_db.queue(element)
                except Exception:  # noqa
                    set_led("ev", "red")
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
                    set_led("ev", "red")
                    mf.syslog_trace(
                        "Unexpected error while trying to commit the queued data "
                        "to the database",
                        syslog.LOG_ALERT,
                        DEBUG,
                    )
                    mf.syslog_trace(traceback.format_exc(), syslog.LOG_ALERT, DEBUG)
                    raise  # may be changed to pass if errors can be corrected.

            pause_interval = (
                sample_interval
                - (time.time() - start_time)  # time spent in this loop  eg. (40-3) = 37s
                - (start_time % sample_interval)  # number of seconds to next loop eg. 3 % 60 = 3s
            )
            # allow the charger to update the data on the server.
            pause_interval += constants.ZAPPI["delay"]
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

            new_start_dt = sql_db.latest_datapoint()  # type: str
            if new_start_dt < start_dt or not data:
                # there is a hole in the data
                mf.syslog_trace(
                    f"Found a hole in the data between {start_dt} and {new_start_dt}.",
                    syslog.LOG_WARNING,
                    DEBUG,
                )
                dati = dt.datetime.strptime(new_start_dt, constants.DT_FORMAT) + dt.timedelta(
                    days=lookahead_days
                )

                if dati > dt.datetime.today():
                    mf.syslog_trace(
                        f"Can't jump to {dati.strftime('%Y-%m-%d')} in the future.",
                        syslog.LOG_WARNING,
                        DEBUG,
                    )
                    dati = dt.datetime.today()
                start_dt = dati.strftime("%Y-%m-%d %H:%M:%S")
                mf.syslog_trace(
                    f"Attempting to cross it at {start_dt}.", syslog.LOG_WARNING, DEBUG
                )
                # if we don't cross the gap then next time check more days ahead
                lookahead_days += 1
                if DEBUG:
                    pause_interval = 10
            else:
                start_dt = new_start_dt
                lookahead_days = 1

            _d = (
                dt.datetime.now() - dt.datetime.strptime(new_start_dt, constants.DT_FORMAT)
            ) / dt.timedelta(days=1)
            if _d > 7.0:
                pause_interval = pause_interval / 10

            # gives the actual time when the next loop should start
            next_time = pause_interval + time.time()

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


def do_work(zappi, start_dt=dt.datetime.today()) -> list:
    """

    Args:
        zappi (obj): object of class Myenergi
        start_dt (datetime): date/time for which to retrieve data

    Returns:
        (list) list of dicts containing data retrieved
    """
    zappi.fetch_data(start_dt)

    #
    # {'sample_time': '2022-04-30 08:37:00', 'sample_epoch': 1651300620, 'site_id': 4.1,
    # 'exp': 300, 'gen': 0.0, 'gep': 24180, 'imp': 1860, 'h1b': 0.0, 'h1d': 0.0,
    # 'v1': 2245, 'frq': 5001
    # }
    #
    _ret: list = zappi.zappi_data
    return _ret


def set_led(dev, colour) -> None:
    mf.syslog_trace(f"{dev} is {colour}", False, DEBUG)

    in_dirfile = f"{APPROOT}/www/{colour}.png"
    out_dirfile = f'{constants.TREND["website"]}/{dev}.png'
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
