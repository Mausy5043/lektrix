#!/usr/bin/env bash

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)

last_month=$(date -d "$(date +%Y-%m-15) -1 month" +%m-%Y)
pushd "${HERE}" >/dev/null || exit 1
    ./trendhw.py --months 6 --debug > "../data/hw-report_${last_month}.txt"
popd >/dev/null || exit
