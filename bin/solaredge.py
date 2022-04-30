#!/usr/bin/env python3
"""Daemon to periodically call the SolarEdge API to fetch energy production data.

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

import libsolaredge as sl

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

# example values:
# HERE: ['', 'home', 'pi', 'lektrix', 'bin', 'solaredge.py']
# MYID: 'solaredge.py
# MYAPP: lektrix
# MYROOT: /home/pi
# NODE: rbelec

API_SE = sl.Solaredge('000000')


def main():
    """Execute main loop until killed."""
    global API_SE
    killer = ml.GracefulKiller()
    iniconf = configparser.ConfigParser()
    # read api_key from the file ~/.config/solaredge/account.ini
    iniconf.read(f"{os.environ['HOME']}/.config/solaredge/account.ini")
    api_key = iniconf.get("account", "api_key")
    API_SE = sl.Solaredge(api_key)

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
        if time.time() > next_time:
            start_time = time.time()
            start_dt = sql_db.latest_datapoint()

            if not site_list:
                try:
                    site_list = API_SE.get_list()["sites"]["site"]
                except Exception:   # noqa
                    mf.syslog_trace("Error connecting to SolarEdge", syslog.LOG_CRIT, DEBUG)
                    mf.syslog_trace(traceback.format_exc(), syslog.LOG_CRIT, DEBUG)
                    site_list = []
                    pass

            if site_list:
                try:
                    data = do_work(site_list, start_dt=dt.datetime.strptime(start_dt, constants.DT_FORMAT))
                except Exception:   # noqa
                    mf.syslog_trace("Unexpected error while try to do some work!", syslog.LOG_CRIT, DEBUG)
                    mf.syslog_trace(traceback.format_exc(), syslog.LOG_CRIT, DEBUG)
                    raise
                if data:
                    try:
                        mf.syslog_trace(f"Data to add (first) : {data[0]}", False, DEBUG)
                        mf.syslog_trace(f"            (last)  : {data[-1]}", False, DEBUG)
                        for element in data:
                            sql_db.queue(element)
                    except Exception:  # noqa
                        mf.syslog_trace("Unexpected error while try to queue the data", syslog.LOG_ALERT, DEBUG)
                        mf.syslog_trace(traceback.format_exc(), syslog.LOG_ALERT, DEBUG)
                        raise  # may be changed to pass if errors can be corrected.
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


def do_work(site_list, start_dt=dt.datetime.today()):
    """Extract the data from the dict(s)."""
    back_dt = start_dt - dt.timedelta(days=1)
    result_dict = constants.SOLAREDGE['template']
    data_dict = dict()
    data_list = list()
    result_list = list()

    for site in site_list:
        site_id = site['id']
        try:
            data_dict = API_SE.get_overview(site_id)['overview']
            data_list = API_SE.get_energy_details(id,
                                                  dt.datetime.strftime(back_dt, constants.DT_FORMAT),
                                                  dt.datetime.strftime(start_dt, constants.DT_FORMAT),
                                                  time_unit="QUARTER_OF_AN_HOUR"
                                                  )['energyDetails']['meters'][0]['values']
        except Exception:  # noqa
            mf.syslog_trace("Request was unsuccesful.", syslog.LOG_WARNING, DEBUG)
            mf.syslog_trace(traceback.format_exc(), syslog.LOG_WARNING, DEBUG)
            mf.syslog_trace("Maybe next time...", syslog.LOG_WARNING, DEBUG)

        """
        data_list looks like this:
        [{'date': '2022-04-30 05:15:00'},
         {'date': '2022-04-30 05:30:00'},
         {'date': '2022-04-30 05:45:00'},
         {'date': '2022-04-30 06:00:00'},
         {'date': '2022-04-30 06:15:00', 'value': 0.0},
         {'date': '2022-04-30 06:30:00', 'value': 2.0},
         {'date': '2022-04-30 06:45:00', 'value': 10.0}
         ...
        ]
        """
        if data_list:
            for element in data_list:
                date_time = element['date']
                try:
                    energy = element['value']
                except KeyError:
                    energy = 0

                result_dict['sample_time'] = date_time
                result_dict['sample_epoch'] = int(dt.datetime.strptime(date_time, constants.DT_FORMAT).timestamp())
                result_dict['site_id'] = site_id
                result_dict['energy'] = energy
                mf.syslog_trace(f"    : {date_time} = {energy}", False, DEBUG)
                result_list.append(result_dict)
    return result_list


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
