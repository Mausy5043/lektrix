#!/usr/bin/env python3

import argparse
import os
import syslog
import time

import mausy5043funcs.fileops3 as mf
import mausy5043libs.libsignals3 as ml

parser = argparse.ArgumentParser(description="Execute the zappi daemon.")
parser_group = parser.add_mutually_exclusive_group(required=True)
parser_group.add_argument("--start",
                          action="store_true",
                          help="start the daemon as a service"
                          )
parser_group.add_argument("--debug",
                          action="store_true",
                          help="start the daemon in debugging mode"
                          )
OPTION = parser.parse_args()

# constants
DEBUG = False
HERE = os.path.realpath(__file__).split("/")
# runlist id :
MYID = HERE[-1]
# app_name :
MYAPP = HERE[-3]
MYROOT = "/".join(HERE[0:-3])
# host_name :
NODE = os.uname()[1]


# example values:
# HERE: ['', 'home', 'pi', 'lektrix', 'bin', 'zappi.py']
# MYID: zappi.py
# MYAPP: lektrix
# MYROOT: /home/pi
# NODE: rbelec


def main():
    killer = ml.GracefulKiller()
    while not killer.kill_now:
        time.sleep(5.0)


if __name__ == "__main__":
    # initialise logging
    syslog.openlog(ident=f'{MYAPP}.{MYID.split(".")[0]}', facility=syslog.LOG_LOCAL0)

    if OPTION.debug:
        DEBUG = True
        mf.syslog_trace("Debug-mode started.", syslog.LOG_DEBUG, DEBUG)
        print("Use <Ctrl>+C to stop.")

    # OPTION.start only executes this next line, we don't need to test for it.
    main()

    print("And it's goodnight from him")
