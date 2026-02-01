#!/usr/bin/env bash

MAINTENANCE=${1}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)  # /app/scripts
max_retries=5
retry_delay=32
flag_sql_succes=1
app_data_path="${HERE}/../data"
db_leaf_name="lektrix.v2.sqlite3"
db_full_path="${app_data_path}/${db_leaf_name}"
backup_dir="${app_data_path}/backup"
hourly_backup_dir="${backup_dir}/hourly"
daily_backup_dir="${backup_dir}/daily"
monthly_backup_dir="${backup_dir}/monthly"

execute_sql() {
    local database=$1
    local sql=$2

    flag_sql_succes=1
    for ((i=1; i<=max_retries; i++)); do
        if sqlite3 "${database}" "${sql}"; then
            echo "succesful"
            flag_sql_succes=0
            return 0
        else
            echo "Database error (locked?). Retry $i/$max_retries in $retry_delay seconds..."
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

create_hourly_backup() {
    local timestamp
    local backup_path

    timestamp=$(date +'%Y%m%d_%H%M%S')
    backup_path="${hourly_backup_dir}/${timestamp}_${db_leaf_name}"
    echo "___ creating hourly backup..."
    cp -v "${db_full_path}" "${backup_path}"

    # Cleanup: Keep only the last 24 hourly backups
    find "${hourly_backup_dir}" -type f -name '*.sqlite3' -printf '%T@ %p\n' | \
        sort -n | \
        head -n -24 | \
        while read -r ts old_backup; do
            rm -f "${old_backup}"
            echo "___ removed old hourly backup: ${ts} = ${old_backup}"
        done
}

create_daily_backup() {
    local timestamp
    local daily_backup_path
    local compressed_backup_path

    timestamp=$(date +'%Y%m%d')
    daily_backup_path="${daily_backup_dir}/${timestamp}_${db_leaf_name}"
    compressed_backup_path="${daily_backup_path}.bz2"

    # Create uncompressed daily backup
    echo "___ creating compressed daily backup..."
    cp -v "${db_full_path}" "${daily_backup_path}"
    bzip2 -9 -v "${daily_backup_path}"

    # Cleanup: Keep only the last 31 daily backups
    find "${daily_backup_dir}" -type f -name '*.bz2' -printf '%T@ %p\n' | \
        sort -n | \
        head -n -31 | \
        while read -r ts old_backup; do
            rm -f "${old_backup}"
            echo "___ removed old daily backup: ${ts} = ${old_backup}"
        done
}

create_monthly_backup() {
    local timestamp
    local daily_backup_path
    # local compressed_backup_path

    timestamp=$(date +'%Y%m')
    monthly_backup_path="${monthly_backup_dir}/${timestamp}_${db_leaf_name}"
    # compressed_backup_path="${monthly_backup_path}.bz2"

    # Create uncompressed daily backup
    echo "___ creating compressed monthly backup..."
    cp -v "${db_full_path}" "${monthly_backup_path}"
    bzip2 -9 -v "${monthly_backup_path}"

    # TODO: move backup to remote location

    # Cleanup: Keep only the last 14 monthly backups
    find "${monthly_backup_dir}" -type f -name '*.bz2' -printf '%T@ %p\n' | \
        sort -n | \
        head -n -14 | \
        while read -r ts old_backup; do
            rm -f "${old_backup}"
            echo "___ removed old monthly backup: ${ts} = ${old_backup}"
        done

    # ### PURGE OLD DATA ###
    # !!!this code disabled for now!!!
    # Keep upto 20 years of data           (yr   day   hr   sec )
    # CURRENT_EPOCH=$(date +'%s')
    # PURGE_EPOCH=$(echo "${CURRENT_EPOCH} - (20 * 366 * 24 * 3600)" | bc)
    # echo -n "${db_full_path} vacuuming... "
    # echo "${PURGE_EPOCH}"
    # execute_sql "${db_full_path}" "DELETE FROM mains WHERE sample_epoch < ${PURGE_EPOCH};"
    # execute_sql "${db_full_path}" "DELETE FROM production WHERE sample_epoch < ${PURGE_EPOCH};"
    # execute_sql "${db_full_path}" "DELETE FROM prices WHERE sample_epoch < ${PURGE_EPOCH};"
}

pushd "${HERE}" >/dev/null || exit 1
    # shellcheck disable=SC1091
    if [ "${MAINTENANCE}" == "-maintenance" ]; then
        # do some maintenance
        echo "...Starting lektrix database maintenance..."

        # ### HOURLY MAINTENANCE ###
        echo -n "___ ${db_full_path} integrity check:   "
        execute_sql "${db_full_path}" "PRAGMA integrity_check;"

        if [ "${flag_sql_succes=1}" == 0 ]; then
            # integrity check was succesful, safe to make a backup
            create_hourly_backup

            # ### DAILY MAINTENANCE ###
            # run once per day:
            if [ "$(date +'%H')" -eq 0 ]; then
                echo -n "___ ${db_full_path} daily ANALYZE  :   "
                execute_sql "${db_full_path}" "ANALYZE;"

                if [ "${flag_sql_succes=1}" == 0 ]; then
                    echo "ok"
                    # 'analyze' was succesful, also make a daily backup
                    create_daily_backup
                else
                    echo "ANALYZE failed! Aborting..." >&2
                    exit 1
                fi

                # ### MONTHLY MAINTENANCE ###
                # run once per month:
                if [ "$(date +'%d')" -eq 1 ]; then
                    create_monthly_backup
                    now=$(date +'%Y%m')
                    ./trendhw.py --months 14 --debug > "${app_data_path}/report_${now}.txt"
                fi
            fi

        else
            echo "Database integrity check failed. Aborting..." >&2
            exit 1
        fi
        # exit 0  # skip trending when doing maintenance
    fi

    ./trendhw.py --hours 0 --days 0 --months 0 --years 0

    ./trendprice.py --twoday

popd >/dev/null || exit
