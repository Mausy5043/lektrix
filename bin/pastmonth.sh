#!/usr/bin/env bash

# query daily totals for a period of one month

MAINTENANCE=${1}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)
max_retries=5
retry_delay=32
flag_sql_succes=1

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

pushd "${HERE}" >/dev/null || exit 1
# shellcheck disable=SC1091
source ./include.sh

if [ "${MAINTENANCE}" == "-" ]; then
    # do some maintenance
    CURRENT_EPOCH=$(date +'%s')

    # shellcheck disable=SC2154
    echo "${db_full_path} re-indexing... "
    execute_sql "${db_full_path}" "REINDEX;"

    echo -n "${db_full_path} integrity check:   "
    execute_sql "${db_full_path}" "PRAGMA integrity_check;"
    if [ "${flag_sql_succes=1}" == 0 ]; then
        echo "${db_full_path} copying to backup... "
        # copy to backup
        if command -v rclone &> /dev/null; then
            # shellcheck disable=SC2154
            rclone copyto -v \
                   "${database_local_root}/${app_name}/${database_filename}" \
                   "${database_remote_root}/backup/${database_filename}"
        fi

        # Keep upto 10 years of data
        echo "${db_full_path} vacuuming... "
        PURGE_EPOCH=$(echo "${CURRENT_EPOCH} - (3660 * 24 * 3600)" | bc)
        execute_sql "${db_full_path}" "DELETE FROM mains WHERE sample_epoch < ${PURGE_EPOCH};"
        execute_sql "${db_full_path}" "DELETE FROM production WHERE sample_epoch < ${PURGE_EPOCH};"
        execute_sql "${db_full_path}" "DELETE FROM prices WHERE sample_epoch < ${PURGE_EPOCH};"
    else
        echo "Database integrity check failed. Skipping backup and vacuuming." >&2
    fi
    # sync the database into the cloud
    if command -v rclone &> /dev/null; then
        echo "${db_full_path} syncing... "
        # shellcheck disable=SC2154
        rclone copyto -v \
               "${database_local_root}/${app_name}/${database_filename}" \
               "${database_remote_root}/${app_name}/${database_filename}"
    fi
fi

./trendhw.py --days 0

popd >/dev/null || exit
