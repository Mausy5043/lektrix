#!/usr/bin/env bash

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)
PASTDAY_IMAGE='/tmp/kamstrupd/site/img/kam_pastday.png'


pushd "${HERE}" >/dev/null || exit 1
    echo "no graphing defined"
    if [ ! -f ${PASTDAY_IMAGE} ]; then
        cp "${HERE}/fles/static/empty.png" ${PASTDAY_IMAGE}
    fi
    # ./trend.py --hours 0
popd >/dev/null || exit
