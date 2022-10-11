#!/usr/bin/env bash

# query monthly totals for a period of n years

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)

pushd "${HERE}" >/dev/null || exit 1

./ms-trend.py --months 0 --years 0
./trendyg.py --months 0 --gauge 0
# ./lg-trend.py --months 0 --years 0

popd >/dev/null || exit
