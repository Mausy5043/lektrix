#!/usr/bin/env bash

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)  # /app/scripts

echo "Collecting data..."

pushd "${HERE}" >/dev/null || exit 1
    /app/scripts/sessy.py --single &
    /app/scripts/solaredge-v1.py --single &
    /app/scripts/wizkwh.py --single &
    wait
popd >/dev/null || exit 1

echo "Data collection done."
