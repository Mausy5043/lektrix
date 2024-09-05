#!/usr/bin/env python3

import os
import sys

import pytz
from sh import CommandNotFound, git

_MYHOME: str = os.environ["HOME"]
_DATABASE_FILENAME: str = "lektrix.sqlite3"
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
    "hour_graph_v2": f"{_WEBSITE}/lex_pasthours",
    "day_graph_v2": f"{_WEBSITE}/lex_pastdays",
    "month_graph_v2": f"{_WEBSITE}/lex_pastmonths",
    "year_graph_v2": f"{_WEBSITE}/lex_pastyears",
    "yg_vs_month_v2": f"{_WEBSITE}/lex_vs_month",
    "yg_gauge_v2": f"{_WEBSITE}/lex_gauge",
}

KAMSTRUP: dict = {
    "database": _DATABASE,
    "sql_table": "mains",
    "sql_command": "INSERT INTO mains ("
                   "sample_time, sample_epoch, "
                   "T1in, T2in, powerin, "
                   "T1out, T2out, powerout, "
                   "tarif, swits"
                   ");"
                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    "report_interval": 900,
    "samplespercycle": 88,  # meter runs at 1 telegram every ~10s
    "delay": 0,
    "template": {
        "sample_time": "dd-mmm-yyyy hh:mm:ss",
        "sample_epoch": 0,
        "T1in": 0,
        "T2in": 0,
        "powerin": 0,
        "T1out": 0,
        "T2out": 0,
        "powerout": 0,
        "tarif": 1,
        "swits": 1,
    },
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
        "energy": 0,
    },
}

ZAPPI: dict = {
    "database": _DATABASE,
    "sql_table": "charger",
    "sql_command": "INSERT INTO charger ("
                   "sample_time, sample_epoch, site_id,"
                   "exp, gen, gep, imp, h1b, h1d,"
                   "v1, frq"
                   ");"
                   "VALUES (?, ?, ?,"
                   "?, ?, ?, ?, ?, ?,"
                   "?, ?"
                   ")",
    "report_interval": int(60 * 60 * 24 / 365 * 10),
    "samplespercycle": 1,
    "delay": 180,
    "director": "https://director.myenergi.net",
    "requests_timeout": 30,
    "template": {
        "sample_time": "yyyy-mm-dd hh:mm:ss",
        "sample_epoch": 0,
        "site_id": 4.1,
        "hr": 0,
        "min": 0,
        # 'dow': "Mon",
        "dom": 1,
        "mon": 8,
        "yr": 2021,
        "exp": 0,
        "gen": 0,
        "gep": 0,
        "imp": 0,
        "h1b": 0,
        "h1d": 0,
        "v1": 0,
        # 'pect1': 0,
        # 'pect2': 0,
        # 'pect3': 0,
        # 'nect1': 0,
        # 'nect2': 0,
        # 'nect3': 0,
        "frq": 0,
    },
    "template_keys_to_drop": ["yr", "mon", "dom", "hr", "min"],
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
