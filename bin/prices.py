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

# Read the API key and URL from the INI file
config_file = cs.PRICES["config"]
config = configparser.ConfigParser()
try:
    # Reading the INI config file
    with open(config_file) as file:
        config.read_file(file)
    api_key: str = config.get("API", "key", fallback="")
    url: str = config.get("API", "url", fallback="")
    savefile: str = os.path.expanduser(
        config.get(
            "API",
            "saveto",
        )
    )
    if not api_key or not url:
        print("API key or URL missing in the configuration.")
        sys.exit(1)
except FileNotFoundError:
    print(f"Config file not found: {config_file}")
    sys.exit(1)
except configparser.Error as her:
    print(f"Error processing config file: {her}")
    sys.exit(1)


# Get the data from the API

params = {"period": "vandaag", "type": "json", "key": api_key}
# period=jaar&year=2013
try:
    response = requests.get(url, timeout=10.0, params=params)
    response.raise_for_status()  # Raise an exception for HTTP errors
    # Parse the JSON data
    now_data = response.json()
    # print(json.dumps(resp_data, indent=4))
except requests.exceptions.RequestException as her:
    print(f"An error occurred: {her}")
    now_data = []

params = {"period": "morgen", "type": "json", "key": api_key}
# period=jaar&year=2013
try:
    response = requests.get(url, timeout=10.0, params=params)
    response.raise_for_status()  # Raise an exception for HTTP errors
    # Parse the JSON data
    nxt_data = response.json()
    # print(json.dumps(resp_data, indent=4))
except requests.exceptions.RequestException as her:
    print(f"An error occurred: {her}")
    nxt_data = []

resp_data = now_data + nxt_data
# Convert the data for the database
data: list = []
for item in resp_data:
    try:
        sample_time = item['datum']
        price = float(item['prijs_excl_belastingen'].replace(',', '.'))
        sample_epoch = int(pd.Timestamp(sample_time).timestamp())
        data.append({"sample_time": sample_time, "sample_epoch": sample_epoch, "price": price})
    except (KeyError, ValueError, TypeError) as her:
        print(f"Error processing item: {item}, error: {her}")

# Save the data to a JSON file
with open(savefile, 'w', encoding='utf-8') as _f:
    json.dump(data, _f, ensure_ascii=True, indent=4)

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
