#!/usr/bin/env python3

# lektrix
# Copyright (C) 2025  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

import configparser
import json
import os

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
    api_key: str = config.get("API", "key")
    url: str = config.get("API", "url")
    savefile: str = os.path.expanduser(config.get("API", "saveto"))
except (FileNotFoundError, configparser.Error) as e:
    print(f"Error reading config file: {e}")
    exit(1)

# Get the data from the API
params = {"period": "morgen", "type": "json", "key": api_key}
# period=jaar&year=2013
resp_data: list[dict] = []
try:
    response = requests.get(url, timeout=10.0, params=params)
    response.raise_for_status()  # Raise an exception for HTTP errors
    # Parse the JSON data
    resp_data = response.json()
    # print(json.dumps(resp_data, indent=4))
except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")

# Convert the data for the database
data: list[dict] = []
for item in resp_data:
    price = float(item['prijs_excl_belastingen'].replace(',', '.'))
    sample_time = item['datum']
    sample_epoch = int(pd.Timestamp(sample_time).timestamp())
    data.append({"sample_time": sample_time, "sample_epoch": sample_epoch, "price": price})

# Save the data to a JSON file
with open(savefile, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=True, indent=4)

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
