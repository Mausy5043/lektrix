import configparser
import json
import os

import requests

# Read the API key and URL from the INI file
config_file = os.path.expanduser("~/.config/jeroen.conf")
config = configparser.ConfigParser()

try:
    # Reading the INI config file
    with open(config_file) as file:
        config.read_file(file)
    api_key: str = config.get("API", "key")
    url: str = config.get("API", "url")
except (FileNotFoundError, configparser.Error) as e:
    print(f"Error reading config file: {e}")
    exit(1)

params = {"period": "vandaag", "type": "json", "key": api_key}

try:
    response = requests.get(url, params=params)
    response.raise_for_status()  # Raise an exception for HTTP errors
    # Parse the JSON data
    data: list[dict] = response.json()
    print(json.dumps(data, indent=4))
except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")
