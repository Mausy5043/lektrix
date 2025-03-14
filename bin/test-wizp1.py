#!/usr/bin/env python3

# lektrix
# Copyright (C) 2024  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE


import asyncio

from homewizard_energy import HomeWizardEnergyV1
from mausy5043_common import funzeroconf as zcd

# get a HomeWizard IP
_howip = zcd.get_ip("_hwenergy", filtr="HWE-P1")

IP_ADDRESS = "0.0.0.0"  # nosec - B104: hardcoded_bind_all_interfaces
if _howip:
    IP_ADDRESS = _howip[0]


async def async_work():
    async with HomeWizardEnergyV1(host=IP_ADDRESS) as api:
        # blink the LED on the device
        await api.identify()

        wiz_host = api.host  # call function
        print("\nhost")
        print(wiz_host, api.host)  # function return-value and class parameter should be same

        # Get device information, like firmware version
        wiz_dev = await api.device()
        print("\ndevice")
        print(wiz_dev)

        # Get measurements, like energy or water usage
        wiz_data = await api.measurement()
        print("\ndata")
        print(wiz_data)
        print(wiz_data.energy_import_kwh)

        # wiz_state = await api.state()
        # print("\nstate")
        # print(wiz_state)

        wiz_system = await api.system()
        print("\nsystem")
        print(wiz_system)


asyncio.run(async_work())  # type ignore:[no-untyped-call]
print("\n\nNORMAL\n\n")
