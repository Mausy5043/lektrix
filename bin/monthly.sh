#!/usr/bin/env bash

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)

# shellcheck disable=SC1091
source /home/pi/.pyenvpaths

pushd "${HERE}" >/dev/null || exit 1
    ./trendhw.py --months 6 --debug > /tmp/report.txt
popd >/dev/null || exit

last_month=$(date -d "$(date +%Y-%m-15) -1 month" +%m-%Y)

/home/pi/bin/pymail.py -s "electricity report for ${last_month}" -f /tmp/report.txt
