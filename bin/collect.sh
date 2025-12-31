#!/usr/bin/env bash

TEST="${1}"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)  # /app/scripts

echo "Collecting data..."
pushd "${HERE}" >/dev/null || exit 1
    echo "TEST = ${TEST}"
    # solaredge: 900s -> 900s
    # wizkwh   : 60s -> 300s
    # sessy    : 60s -> 300s
    # sessy.py     &
    solaredge.py --single &
    # wizkwh.py    &
    wait


popd >/dev/null || exit 1
echo "Data collection done."
