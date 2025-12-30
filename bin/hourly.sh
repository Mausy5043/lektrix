#!/usr/bin/env bash

MAINTENANCE=${1}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)  # /app/scripts
max_retries=5
retry_delay=32
flag_sql_succes=1
db_full_path="${HERE}/../data/lektrix.v2.sqlite3"

execute_sql() {
    local sql=$2
    local database=$1
    flag_sql_succes=1
    for ((i=1; i<=max_retries; i++)); do
        if sqlite3 "${database}" "${sql}"; then
            echo "SQL executed successfully: ${sql}"
            flag_sql_succes=0
            return 0
        else
            echo "Database is locked. Retry $i/$max_retries in $retry_delay seconds..."
            sleep $retry_delay
        fi
    done
    echo "Failed to execute SQL after $max_retries attempts: ${sql}"
    return 1
}

scp_db() {
    # copy the database from the remote location using scp with retries
    local source_path="pi@rbmon.lan:/srv/rmt/_databases/lektrix/lektrix.v2.sqlite3"
    local dest_path="/srv/containers/lektrix/data/lektrix.v2.sqlite3"
    flag_sql_succes=1

    for ((i=1; i<=max_retries; i++)); do
        if scp "${source_path}" "${dest_path}"; then
            echo "SCP completed successfully from ${source_path} to ${dest_path}"
            flag_sql_succes=0
            return 0
        else
            echo "SCP failed. Retry $i/$max_retries in $retry_delay seconds..."
            sleep $retry_delay
        fi
    done
    echo "Failed to SCP after $max_retries attempts from ${source_path} to ${dest_path}"
    exit 1
}

pushd "${HERE}" >/dev/null || exit 1
    # shellcheck disable=SC1091
    # source ./include.sh

    if [ "${MAINTENANCE}" == "-" ]; then
        # do some maintenance
        CURRENT_EPOCH=$(date +'%s')
        # fetch a fresh copy of the database
        # this is done by the service on the host because
        # in the container we don't have a connection to the network.
        # scp_db
        # shellcheck disable=SC2154
        echo "${db_full_path} re-indexing... "
        execute_sql "${db_full_path}" "REINDEX;"

        echo -n "${db_full_path} integrity check:   "
        execute_sql "${db_full_path}" "PRAGMA integrity_check;"
        if [ "${flag_sql_succes=1}" == 0 ]; then
            # echo "${db_full_path} copying to backup... "
            # TODO: copy to backup

            # if command -v rclone &> /dev/null; then
            #     # shellcheck disable=SC2154
            #     rclone copyto -v \
            #         "${database_local_root}/${app_name}/${database_filename}" \
            #         "${database_remote_root}/backup/${database_filename}"
            # fi

            # Keep upto 10 years of data
            echo "${db_full_path} vacuuming... "
            PURGE_EPOCH=$(echo "${CURRENT_EPOCH} - (3660 * 24 * 3600)" | bc)
            execute_sql "${db_full_path}" "DELETE FROM mains WHERE sample_epoch < ${PURGE_EPOCH};"
            execute_sql "${db_full_path}" "DELETE FROM production WHERE sample_epoch < ${PURGE_EPOCH};"
            execute_sql "${db_full_path}" "DELETE FROM prices WHERE sample_epoch < ${PURGE_EPOCH};"
        else
            echo "Database integrity check failed. Aborting..." >&2
            exit 1
        fi
    fi

    ./trendhw.py --hours 0
    ./trendhw.py --days 0
    ./trendhw.py --months 0 --years 0

    ./trendprice.py --twoday

popd >/dev/null || exit
