#!/usr/bin/env python3

# lektrix
# Copyright (C) 2024  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

"""Discover Multi-cast devices that support Homewizard."""

import json
import time

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ZeroconfServiceTypes


class MyListener(ServiceListener):
    """
    Overloaded class of zeroconf.ServiceListener

    Examples of output:
    Service DABMAN i205 CDCCai6fu6g4c4ZZ._http._tcp.local. discovered
    ServiceInfo(type='_http._tcp.local.',
                name='DABMAN i205 CDCCai6fu6g4c4ZZ._http._tcp.local.',
                addresses=[b'\xc0\xa8\x02\x95'],
                port=80,
                weight=0,
                priority=0,
                server='http-DABMAN i205 CDCCai6fu6g4c4ZZ.local.',
                properties={b'path': b'/irdevice.xml,CUST_APP=0,BRAND=IMPERIAL,MAC=3475638B4984'},
                interface_index=None)
    ip = 192:168:2:149

    Service RBFILE._smb._tcp.local. discovered
    ServiceInfo(type='_smb._tcp.local.',
                name='RBFILE._smb._tcp.local.',
                addresses=[b'\xc0\xa8\x02\x12'],
                port=445,
                weight=0,
                priority=0,
                server='rbfile.local.',
                properties={b'': None},
                interface_index=None)
    ip = 192:168:2:18

    Service Canon_TS6251._http._tcp.local. discovered
    ServiceInfo(type='_http._tcp.local.',
                name='Canon_TS6251._http._tcp.local.',
                addresses=[b'\xc0\xa8\x02\xf0'],
                port=80,
                weight=0,
                priority=0,
                server='proton3.local.',
                properties={b'txtvers': b'1'},
                interface_index=None)
    ip = 192:168:2:240
    """

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Forget services that disappear during the discovery scan."""
        _name = name.replace(" ", "_")
        __name = _name.split(".")[0]
        print(f"(  -) Service {__name} {type_} disappeared.")
        if __name in DISCOVERED:
            del DISCOVERED[__name]

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Overridden but not used."""
        _name = name.replace(" ", "_")
        __name = _name.split(".")[0]
        __type = type_.split(".")[0]
        print(f"( * ) Service {__name} updated. ( {__type} )")
        # find out updated info about this device
        info = zc.get_service_info(type_, name)
        svc: str = ""
        prop: dict = {}
        if info:
            try:
                prop = self.debyte(info.properties)
                if info.addresses:
                    svc = ".".join(list(map(str, list(info.addresses[0]))))
            except BaseException:
                print(
                    f"Exception for device info: {info}\n {
                        info.properties}\n {
                        info.addresses}\n"
                )
                raise
        if (__name in DISCOVERED) and (__type in DISCOVERED[__name]):
            DISCOVERED[__name][__type] = {
                "ip": svc,
                "name": name,
                "type": type_,
                "properties": prop,
            }

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Remember services that are discovered during the scan."""
        _name = name.replace(" ", "_")
        __name = _name.split(".")[0]
        __type = type_.split(".")[0]
        # find out more about this device
        info = zc.get_service_info(type_, name)
        svc: str = ""
        prop: dict = {}
        if info:
            try:
                prop = self.debyte(info.properties)
                if info.addresses:
                    svc = ".".join(list(map(str, list(info.addresses[0]))))
            except BaseException:
                print(
                    f"Exception for device info: {info}\n {
                        info.properties}\n {
                        info.addresses}\n"
                )
                raise
        print(f"(+  ) Service {__name} discovered ( {__type} ) on {svc}")
        # register the device
        if __name not in DISCOVERED:
            DISCOVERED[__name] = {
                f"{__type}": {
                    "ip": svc,
                    "name": name,
                    "type": type_,
                    "properties": prop,
                }
            }
        # additional services discovered for an already discovered device
        if __type not in DISCOVERED[__name]:
            DISCOVERED[__name][__type] = {
                "ip": svc,
                "name": name,
                "type": type_,
                "properties": prop,
            }

    @staticmethod
    def debyte(bytedict: dict[bytes, bytes | None]) -> dict:
        normdict = {}
        if bytedict:
            # bytedict may be empty or None
            for _y in bytedict.keys():
                _x = bytedict[_y]
                # value None can't be decoded
                if _x:
                    normdict[_y.decode("ascii")] = _x.decode("ascii")
                else:
                    # protect against empty keys
                    if _y:
                        normdict[_y.decode("ascii")] = None
        return normdict


def load_discovery():
    print("loading...")
    return {}


def save_discovery(disco_dict):
    print(json.dumps(disco_dict, indent=4))
    print("saving...")


# we keep a registry of discovered devices
DISCOVERED: dict = load_discovery()

_zc = Zeroconf()
_ls = MyListener()

# for testing: discover everything
service_list = ZeroconfServiceTypes.find()
N = 0
browsers = []
for _service in service_list:
    print(f"(   ) Listening for service: {_service}")
    browsers.append(ServiceBrowser(_zc, _service, _ls))

# for reals
# browser1 = ServiceBrowser(_zc, "_hwenergy._tcp.local.", _ls)  # api v1
# browser2 = ServiceBrowser(_zc, "_homewizard._tcp.local.", _ls)  # api v2
# # for testing
# browser3 = ServiceBrowser(_zc, "_smb._tcp.local.", _ls)
# browser4 = ServiceBrowser(_zc, "_http._tcp.local.", _ls)
# browser5 = ServiceBrowser(_zc, "_https._tcp.local.", _ls)

t0: float = time.time()
dt: float = 0.0
while dt < 60.0:
    dt = time.time() - t0

_zc.close()

save_discovery(DISCOVERED)
