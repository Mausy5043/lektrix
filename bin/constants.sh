#!/bin/bash

# shellcheck disable=SC2034
app_name="lektrix"
if [ -f "${HOME}/.${app_name}.branch" ]; then
    branch_name=$(<"${HOME}/.${app_name}.branch")
else
    branch_name="master"
fi
# Python library of common functions
commonlibbranch="v1_0"

# determine machine identity
host_name=$(hostname)

# construct database paths
database_filename="lektrix.sqlite3"
database_path="/srv/databases"
db_full_path="${database_path}/${database_filename}"

# list of timers provided
declare -a lektrix_timers=("lektrix.trend.day.timer" \
                           "lektrix.trend.month.timer" \
                           "lektrix.trend.year.timer" \
                            "lektrix.update.timer")
# list of services provided
declare -a lektrix_services=("lektrix.kamstrup.service" \
                             "lektrix.zappi.service" \
                             "lektrix.solaredge.service" \
                             "lektrix.fles.service")
# Install python3 and develop packages
# Support for matplotlib & numpy needs to be installed seperately
# Support for serial port
# SQLite3 support (incl python3)
declare -a lektrix_apt_packages=("build-essential" "python3" "python3-dev" "python3-pip" \
                                 "libatlas-base-dev" "libxcb1" "libopenjp2-7" "libtiff5" \
                                 "picocom" "python3-serial"
                                 "sqlite3")

# start the application
start_lektrix(){
    echo "Starting ${app_name} on $(date)"
    # make sure /tmp environment exists
    boot_lektrix
    action_timers start
    action_services start
}

# stop, update the repo and start the application
# do some additional stuff when called by systemd
restart_lektrix(){
    ROOT_DIR=$1
    # restarted by update..service or using --graph
    SYSTEMD_REQUEST=$2

    echo "Restarting ${app_name} on $(date)"
    stop_lektrix

    # update the repository
    git fetch origin || sleep 60; git fetch origin
    DIFFLIST=$(git --no-pager diff --name-only "${branch_name}..origin/${branch_name}")
    git pull
    git fetch origin
    git checkout "${branch_name}"
    git reset --hard "origin/${branch_name}" && git clean -f -d

    if [ "${SYSTEMD_REQUEST}" -eq 1 ]; then
        echo "Creating graphs [1]"
        . "${ROOT_DIR}/bin/pastday.sh"
        echo "Creating graphs [2]"
        . "${ROOT_DIR}/bin/pastmonth.sh"
        echo "Creating graphs [3]"
        . "${ROOT_DIR}/bin/pastyear.sh"
    else
        echo "Skipping graph creation"
    fi

    # re-install services and timers in case they were changed
    sudo cp "${ROOT_DIR}"/services/*.service /etc/systemd/system/
    sudo cp "${ROOT_DIR}"/services/*.timer /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl reset-failed

    start_lektrix
}

# stop the application
stop_lektrix(){
    echo "Stopping ${app_name} on $(date)"
    action_timers stop
    action_services stop
}

# uninstall the application
unstall_lektrix(){
    echo "Uninstalling ${app_name} on $(date)"
    stop_lektrix
    action_timers disable
    action_services disable
    action_timers rm
    action_services rm
    rm "${HOME}/.${app_name}.branch"
}

# install the application
install_lektrix(){
    ROOT_DIR=$1

    # to suppress git detecting changes by chmod
    git config core.fileMode false
    # note the branchname being used
    if [ ! -e "${HOME}/.${app_name}.branch" ]; then
        echo "${branch_name}" >"${HOME}/.${app_name}.branch"
    fi

    echo "Installing ${app_name} on $(date)"
    # install APT packages
    for PKG in "${lektrix_apt_packages[@]}"; do
        action_apt_install "${PKG}"
    done
    # install Python3 stuff
    python3 -m pip install --upgrade pip setuptools wheel
    python3 -m pip install -r requirements.txt
    echo
    echo "Uninstall common python functions..."
    python3 -m pip uninstall -y mausy5043-common-python
    echo
    echo "Install common python functions..."
    python3 -m pip install "git+https://gitlab.com/mausy5043-installer/mausy5043-common-python.git@${commonlibbranch}#egg=mausy5043-common-python"

    # install account keys from local fileserver
    getfilefromserver "solaredge" "0740"
    getfilefromserver "zappi" "0740"

    # install services and timers
    sudo cp "${ROOT_DIR}"/services/*.service /etc/systemd/system/
    sudo cp "${ROOT_DIR}"/services/*.timer /etc/systemd/system/
    sudo systemctl daemon-reload
    action_timers enable
    action_services enable

    echo "Installation complete. To start the application use:"
    echo "   lektrix --go"
    # start_lektrix
}

# set-up the application
boot_lektrix(){
    # make sure Flask tree exists
    if [ ! -d "/tmp/${app_name}/site/img" ]; then
        mkdir -p "/tmp/${app_name}/site/img"
        chmod -R 755 "/tmp/${app_name}"
    fi
}

# perform systemctl actions on all timers
action_timers(){
    ACTION=$1
    for TMR in "${lektrix_timers[@]}"; do
        if [ "${ACTION}" != "rm" ]; then
            sudo systemctl "${ACTION}" "${TMR}"
        else
            rm "/etc/systemd/system/${TMR}"
        fi
    done
    sudo systemctl daemon-reload
    sudo systemctl reset-failed
}

# perform systemctl actions on all services
action_services(){
    ACTION=$1
    for SRVC in "${lektrix_services[@]}"; do
        if [ "${ACTION}" != "rm" ]; then
            sudo systemctl "${ACTION}" "${SRVC}"
        else
            rm "/etc/systemd/system/${SRVC}"
        fi
    done
    sudo systemctl daemon-reload
    sudo systemctl reset-failed
}

# See if packages are installed and install them using apt-get
action_apt_install(){
    PKG=$1
    echo "*********************************************************"
    echo "* Requesting ${PKG}"
    status=$(dpkg -l | awk '{print $2}' | grep -c -e "^${PKG}$")
    if [ "${status}" -eq 0 ]; then
        echo "* Installing ${PKG}"
        echo "*********************************************************"
        sudo apt-get -yqq install "${PKG}"
    else
        echo "* Already installed !!!"
        echo "*********************************************************"
    fi
    echo
}

# copy files from the network to the local .config folder
getfilefromserver() {
    file="${1}"
    mode="${2}"

    cp -rvf "/srv/config/${file}" "${HOME}/.config/"
    chmod -R "${mode}" "${HOME}/.config/${file}"
}
