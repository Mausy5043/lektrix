#!/usr/bin/env python3

# lektrix
# Copyright (C) 2024  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE


import asyncio
import json
import sys

import constants as cs
from homewizard_energy import HomeWizardEnergyV1, HomeWizardEnergyV2
from mausy5043_common import funzeroconf as zcd

p1cfg_file = cs.WIZ_P1["config"]
try:
    with open(p1cfg_file) as _f:
        p1cfg = json.load(_f)
except json.decoder.JSONDecodeError:
    print(f"Error reading {p1cfg_file}")
    sys.exit(1)
try:
    TOKEN = p1cfg["token"]
    USER = p1cfg["user"]
    NAME = p1cfg["name"]
    ID = p1cfg["id"]
except KeyError:
    print(f"Error extracting info from {p1cfg}")
    sys.exit(1)

# get a HomeWizard IP
_howip = zcd.get_ip("_hwenergy", filtr="HWE-P1")
IP_ADDRESS = "0.0.0.0"  # nosec - B104: hardcoded_bind_all_interfaces
if _howip:
    IP_ADDRESS = _howip[0]


async def async_work():
    async with HomeWizardEnergyV1(host=IP_ADDRESS) as api1:
        # blink the LED on the device
        await api1.identify()

        wiz_host = api1.host  # call function
        print("\nhost (v1)")
        print(wiz_host, api1.host)  # function return-value and class parameter should be same

        # Get device information, like firmware version
        wiz_dev = await api1.device()
        print("\ndevice (v1)")
        print(wiz_dev)

        # Get measurements, like energy or water usage
        wiz_data = await api1.measurement()
        print("\ndata (v1)")
        print(wiz_data)
        print(wiz_data.energy_import_kwh)

        # wiz_state = await api.state()
        # print("\nstate")
        # print(wiz_state)

        wiz_system = await api1.system()
        print("\nsystem (v1)")
        print(wiz_system)

    async with HomeWizardEnergyV2(host=IP_ADDRESS, token=TOKEN) as api2:
        # blink the LED on the device
        await api2.identify()

        wiz_host = api2.host  # call function
        print("\nhost (v2)")
        print(wiz_host, api2.host)  # function return-value and class parameter should be same

        # Get device information, like firmware version
        wiz_dev = await api2.device()
        print("\ndevice (v2)")
        print(wiz_dev)

        # Get measurements, like energy or water usage
        wiz_data = await api2.measurement()
        print("\ndata (v2)")
        print(wiz_data)
        print(wiz_data.energy_import_kwh)

        # wiz_state = await api.state()
        # print("\nstate")
        # print(wiz_state)

        wiz_system = await api2.system()
        print("\nsystem (v2)")
        print(wiz_system)


asyncio.run(async_work())  # type ignore:[no-untyped-call]
print("\n\nNORMAL\n\n")
