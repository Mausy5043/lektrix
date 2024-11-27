#!/usr/bin/env python3

# lektrix
# Copyright (C) 2024  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

# https://api-documentation.homewizard.com/docs/category/api-v1

import asyncio

from libzeroconf import discover as zcd
from homewizard_energy import HomeWizardEnergyV1

# get a HomeWizard IP
_howip = zcd.get_ip("_hwenergy")

if _howip:
    IP_ADDRESS = _howip[0]


async def main():

    async with HomeWizardEnergyV1(host=IP_ADDRESS) as api:
        # blink the LED on the device
        _ok = await api.identify()

        wiz_host = api.host  # call function
        print("\nhost")
        print(wiz_host, api.host)  # function return-value and class parameter should be same

        # Get device information, like firmware version
        wiz_dev = await api.device()
        print("\ndevice")
        print(wiz_dev)

        # Get measurements, like energy or water usage
        wiz_data = await api.data()
        print("\ndata")
        print(wiz_data)  # .total_energy_import_kwh)

        # Get most recent telegram
        wiz_telegram = await api.telegram()
        print("\ndata")
        print(wiz_telegram)  # .total_energy_import_kwh)

        wiz_state = await api.state()
        print("\nstate")
        print(wiz_state)

        wiz_system = await api.system()
        print("\nsystem")
        print(wiz_system)

        # Turn on the Energy Socket outlet
        # await api.state_set(power_on=True)


asyncio.run(main())
