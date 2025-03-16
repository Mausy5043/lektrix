#!/usr/bin/env python3

# lektrix
# Copyright (C) 2025  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

import configparser
import json
import os

import requests

# Read the API key and URL from the INI file
config_file = os.path.expanduser("~/.config/lektrix/jeroen.conf")
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

params = {"period": "morgen", "type": "json", "key": api_key}
# period=jaar&year=2013

data: list[dict] = []
try:
    response = requests.get(url, timeout=10.0, params=params)
    response.raise_for_status()  # Raise an exception for HTTP errors
    # Parse the JSON data
    data: list[dict] = response.json()
    # print(json.dumps(data, indent=4))
except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")

with open(savefile, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=True, indent=4)
