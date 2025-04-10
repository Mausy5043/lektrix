#!/usr/bin/env python3

import os
import sys

import pytz
from sh import CommandNotFound, git  # type: ignore[import-untyped]

_MYHOME: str = os.environ["HOME"]
_DATABASE_FILENAME: str = "lektrix.v2.sqlite3"
_DATABASE: str = f"/srv/rmt/_databases/lektrix/{_DATABASE_FILENAME}"
_HERE_list: list[str] = os.path.realpath(__file__).split("/")
# ['', 'home', 'pi', 'kimnaty', 'bin', 'constants.py']
_HERE: str = "/".join(_HERE_list[0:-2])
_WEBSITE: str = "/run/lektrix/site/img"

if not os.path.isfile(_DATABASE):
    _DATABASE = f"/srv/databases/{_DATABASE_FILENAME}"
if not os.path.isfile(_DATABASE):
    _DATABASE = f"/srv/data/{_DATABASE_FILENAME}"
if not os.path.isfile(_DATABASE):
    _DATABASE = f"/mnt/data/{_DATABASE_FILENAME}"
if not os.path.isfile(_DATABASE):
    _DATABASE = f".local/{_DATABASE_FILENAME}"
    print(f"Searching for {_DATABASE}")
if not os.path.isfile(_DATABASE):
    # ln -s ~/Dropbox/raspi/_databases/lektrix/ ~/.sqlite/lektrix
    _DATABASE = f"{_MYHOME}/.sqlite3/lektrix/{_DATABASE_FILENAME}"
    print(f"Searching for {_DATABASE}")
if not os.path.isfile(_DATABASE):
    _DATABASE = f"{_DATABASE_FILENAME}"
    print(f"Searching for {_DATABASE}")
if not os.path.isfile(_DATABASE):
    print("Database is missing.")
    sys.exit(1)

if not os.path.isdir(_WEBSITE):
    print("Graphics will be diverted to /tmp")
    _WEBSITE = "/tmp"  # nosec B108

D_FORMAT = "%Y-%m-%d"
DT_FORMAT = "%Y-%m-%d %H:%M:%S"
TIMEZONE = pytz.timezone("Europe/Amsterdam")
FLOAT_FMT = "+.0f"

# fmt: off
BATTERY: dict = {
    "database": _DATABASE,
    "sql_table": "storage",
    "graph_file": ".local/graph.png",
    "sql_command": "INSERT INTO storage ("
                   "sample_time, sample_epoch, battery_id, soc, soh"
                   ") "
                   "VALUES (?, ?, ?, ?)",
    "report_time": 299,
    "samplespercycle": 1,
    "template": {
        "sample_time": "dd-mmm-yyyy hh:mm:ss",
        "sample_epoch": 0,
        "battery_id": 0,
        "soc": None,
        "soh": None,
    },
}

TREND: dict = {
    "database": _DATABASE,
    "website": _WEBSITE,
    "hour_graph": f"{_WEBSITE}/lex_pasthours",
    "day_graph": f"{_WEBSITE}/lex_pastdays",
    "month_graph": f"{_WEBSITE}/lex_pastmonths",
    "year_graph": f"{_WEBSITE}/lex_pastyears",
    "yg_vs_month": f"{_WEBSITE}/lex_vs_month",
    "yg_gauge": f"{_WEBSITE}/lex_gauge",
}

SOLAREDGE: dict = {
    "database": _DATABASE,
    "sql_table": "production",
    "sql_command": "INSERT INTO production ("
                   "sample_time, sample_epoch, site_id, energy"
                   ");"
                   "VALUES (?, ?, ?, ?)",
    "report_interval": 900,  # quarter of an hour resolution
    "samplespercycle": 1,
    "delay": 360,
    "requests_timeout": 30,
    "director": "https://monitoringapi.solaredge.com",
    "template": {
        "sample_time": "yyyy-mm-dd hh:mm:ss",
        "sample_epoch": 0,
        "site_id": 0,
        "solar": 0,
    },
    "config": f"{_MYHOME}/.config/solaredge/account.ini",
}

WIZ_KWH: dict = {
    "database": _DATABASE,
    "sql_table": "mains",
    "sql_command": "INSERT INTO mains ("
                   "sample_time, sample_epoch, site_id,"
                   "exp, imp, gen, gep, evn, evp,"
                   "v1, frq, pf"
                   ");"
                   "VALUES (?, ?, ?,"
                   "?, ?, ?, ?, ?, ?, ?, ?,"
                   "?, ?, ?"
                   ")",
    "report_interval": 900,
    "samplespercycle": 10,
    "delay": 0,
    "template": {
        "sample_time": "yyyy-mm-dd hh:mm:ss",
        "sample_epoch": 0,
        "site_id": 4.2,     # 4.1 = myenergi zappi; 4.2 = HomeWizard
        "exp": 0,
        "imp": 0,
        "gen": 0,
        "gep": 0,
        "evn": 0,
        "evp": 0,
        "v1": 0,
        "frq": 0,
    },
    "config": f"{_MYHOME}/.config/homewizard/kwh.json",
}

PRICES: dict = {
    "database": _DATABASE,
    "sql_table": "prices",
    "sql_command": "INSERT INTO prices ("
                   "sample_time, sample_epoch, "
                   "site_id, price"
                   ");"
                   "VALUES (?, ?, ?, ?)",
    "template": {
        "sample_time": "dd-mmm-yyyy hh:mm:ss",
        "sample_epoch": 0,
        "site_id": "4.2",     # 4.1 = Pure Energie; 4.2 = Tibber
        "price": 0.0,
    },
    "config": f"{_MYHOME}/.config/tibber/account.ini",
    "website": _WEBSITE,
    "twoday_graph": f"{_WEBSITE}/price_twodays",
    "hour_graph": f"{_WEBSITE}/price_pasthours",
    "day_graph": f"{_WEBSITE}/price_pastdays",
    "month_graph": f"{_WEBSITE}/price_pastmonths",
    "year_graph": f"{_WEBSITE}/price_pastyears",
}
# fmt: on


def get_app_version() -> str:
    """Retrieve information of current version of lektrix.

    Returns:
        versionstring
    """
    # git log -n1 --format="%h"
    # git --no-pager log -1 --format="%ai"
    git_args = ["-C", f"{_HERE}", "--no-pager", "log", "-1", "--format='%h'"]
    try:
        _exit_h = git(git_args).strip("\n").strip("'")
    except CommandNotFound as e:
        print(f"Error executing git command: {e}")
        _exit_h = None
    git_args[5] = "--format='%ai'"
    _exit_ai = git(git_args).strip("\n").strip("'")
    return f"{_exit_h}  -  {_exit_ai}"


if __name__ == "__main__":
    print(f"home              = {_MYHOME}")
    print(f"database location = {_DATABASE}")
    print("")
    print(f"lektrix (me)      = {get_app_version()}")
