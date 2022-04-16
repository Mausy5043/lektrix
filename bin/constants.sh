#!/bin/bash

# shellcheck disable=SC2034
app_name="lektrix"

# determine controller's identity
host_name=$(hostname)


# construct database paths
database_filename="lektrix.sqlite3"
database_path="/srv/databases"
db_full_path="${database_path}/${database_filename}"
