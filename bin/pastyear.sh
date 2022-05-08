#!/usr/bin/env bash

# query monthly totals for a period of n years

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)
PASTYEAR_IMAGE='/tmp/kamstrupd/site/img/kam_pastyear.png'
PASTYEARVS_IMAGE='/tmp/kamstrupd/site/img/kam_vs_year.png'
PASTMONTHVS_IMAGE='/tmp/kamstrupd/site/img/kam_vs_month.png'
GAUGE_IMAGE='/tmp/kamstrupd/site/img/kam_gauge.png'

pushd "${HERE}" >/dev/null || exit 1
echo "no graphing defined"
if [ ! -f ${PASTYEAR_IMAGE} ]; then
    cp "${HERE}/fles/static/empty.png" ${PASTYEAR_IMAGE}
    cp "${HERE}/fles/static/empty.png" ${PASTYEARVS_IMAGE}
    cp "${HERE}/fles/static/empty.png" ${PASTMONTHVS_IMAGE}
    cp "${HERE}/fles/static/empty.png" ${GAUGE_IMAGE}
fi
#./trendyg.py --gauge 0 &
#./trend.py --months 0 &
#./trend.py --years 0 &
#./trendyg.py --months 0 &
#wait

popd >/dev/null || exit
