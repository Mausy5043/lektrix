#!/usr/bin/env python3

# lektrix
# Copyright (C) 2025  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

import configparser
import json
import os
import sys

import constants as cs
import pandas as pd
import requests
from mausy5043_common import libsqlite3 as m3

requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]


def req_post(
    _url: str,
    _headers: dict[str, str],
    _payload: dict[str, str],
) -> dict[str, str]:
    """Make a POST request to the given URL with the specified headers and payload."""
    try:
        response = requests.post(
            _url,
            headers=_headers,
            json=_payload,
            timeout=30.0,
            verify=False,  # nosec B501
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as her:
        print(f"An error occurred: {her}")
        return {}


def unpeel(
    _data: dict[str, str],
    _key: str,
) -> list:
    """Unpeel the data from the given key."""
    _l1 = _data["data"]["viewer"]["homes"]
    _l2 = _l1[0]["currentSubscription"]["priceInfo"][_key]
    return _l2


# Read the API key and URL from the INI file
config_file = cs.PRICES["config"]
config = configparser.ConfigParser()
try:
    # Reading the INI config file
    with open(config_file) as file:
        config.read_file(file)
    api_key: str = config.get("API", "key", fallback="")
    api_url: str = config.get("API", "url", fallback="")
    savefile: str = os.path.expanduser(config.get("API", "saveto"))
    qry_now: str = config.get("API", "qry_now", fallback="")
    qry_nxt: str = config.get("API", "qry_nxt", fallback="")
    if not api_key or not api_url:
        print("API key or URL missing in the configuration.")
        sys.exit(1)
except FileNotFoundError:
    print(f"Config file not found: {config_file}")
    sys.exit(1)
except configparser.Error as her:
    print(f"Error processing config file: {her}")
    sys.exit(1)


# Get the today's data from the API
headers_post = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
payload = {"query": qry_now}
now_data = req_post(
    api_url,
    headers_post,
    payload,
)

# Get the tomorrow's data from the API
payload = {"query": qry_nxt}
nxt_data = req_post(
    api_url,
    headers_post,
    payload,
)

resp_data = unpeel(now_data, "today") + unpeel(nxt_data, "tomorrow")
# Convert the data for the database
data: list = []
for item in resp_data:
    try:
        sample_time = item['startsAt'].split(".")[0].replace("T", " ")
        price = float(item['total'])
        sample_epoch = int(pd.Timestamp(sample_time).timestamp())
        data.append({"sample_time": sample_time, "sample_epoch": sample_epoch, "price": price})
    except (KeyError, ValueError, TypeError) as her:
        print(f"Error processing item: {item}, error: {her}")

# Save the data to a JSON file
with open(savefile, 'w', encoding='utf-8') as _f:
    json.dump(data, _f, ensure_ascii=True, indent=4)
# print(json.dumps(data, indent=4))

# Save the data to the database
sql_db = m3.SqlDatabase(
    database=cs.PRICES["database"],
    table=cs.PRICES["sql_table"],
    insert=cs.PRICES["sql_command"],
    debug=True,
)
for element in data:
    sql_db.queue(element)

sql_db.insert(method="replace")
