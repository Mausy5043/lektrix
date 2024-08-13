#!/usr/bin/env python3

"""Common functions for use with the KAMSTRUP electricity meter"""

import datetime as dt
import sqlite3 as s3

import numpy as np


def add_time_line(config: dict) -> dict:
    """Create a numpy array of labels based on the settings in config

    Args:
        config (dict): settings to be used

    Returns:
        dict: Modified version of `config`
    """
    final_epoch = int(dt.datetime.now().timestamp())
    if "year" in config:
        ytf = int(config["year"]) + 1
        final_epoch = int(
            dt.datetime.strptime(f"{ytf}-01-01 00:00", "%Y-%m-%d %H:%M").timestamp()  # noqa: E501
        )
    step_epoch = 15 * 60
    multi = 3600
    if config["timeframe"] == "hour":
        multi = 3600
    if config["timeframe"] == "day":
        multi = 3600 * 24
    if config["timeframe"] == "month":
        multi = 3600 * 24 * 31
    if config["timeframe"] == "year":
        multi = 3600 * 24 * 366
    start_epoch = int((final_epoch - (multi * config["period"])) / step_epoch) * step_epoch
    config["timeline"] = np.arange(start_epoch, final_epoch, step_epoch, dtype="int")
    return config


def get_historic_data(
    dicti, telwerk=None, from_start_of_year=False, include_today=True, dif=True
) -> tuple:
    """Fetch historic data from SQLITE3 database.

    Args:
        dif: whether to treat the data as a cumulative counter or as single values
        include_today (bool): whether or not to include today's data
        dicti (dict): containing settings
        telwerk (str): columnname to be collected
        from_start_of_year (bool): fetch data from start of year or not

    Returns:
        ret_data: numpy list of ints - data returned and numpy list of str - label texts returned
    """
    ytf = 2019
    period = dicti["period"]
    interval = f"datetime('now', '-{period + 1} {dicti['timeframe']}')"
    and_where_not_today = ""
    if from_start_of_year:
        interval = (
            f"datetime(datetime('now', '-{period + 1} {dicti['timeframe']}'), 'start of year')"
        )
    if not include_today:
        and_where_not_today = "AND (sample_time <= datetime('now', '-1 day'))"
    if "year" in dicti:
        ytf = dicti["year"]
        interval = f"datetime('{ytf}-01-01 00:00')"
        and_where_not_today = f"AND (sample_time <= datetime('{ytf + 1}-01-01 00:00'))"

    db_con = s3.connect(dicti["database"])
    with db_con:
        db_cur = db_con.cursor()
        db_cur.execute(
            f"SELECT sample_epoch, "
            f"{telwerk} "
            f"FROM {dicti['table']} "
            f"WHERE (sample_time >= {interval}) "
            f"{and_where_not_today} "
            f"ORDER BY sample_epoch ASC "
            f";"
        )
        db_data = db_cur.fetchall()
    if not db_data:
        # fake some data
        db_data = [
            (int(dt.datetime(ytf, 1, 1).timestamp()), 0),
            (int(dt.datetime(ytf + 1, 1, 1).timestamp()), 0),
        ]

    data = np.array(db_data)
    # interpolate the data to monotonic 10minute intervals provided by dicti['timeline']
    ret_epoch, ret_intdata = interplate(
        dicti["timeline"],
        np.array(data[:, 0], dtype=int),
        np.array(data[:, 1], dtype=int),
    )

    # group the data by dicti['grouping']
    ret_lbls, ret_grpdata = fast_group_data(ret_epoch, ret_intdata, dicti["grouping"], dif=dif)

    ret_data = ret_grpdata / 1000
    return ret_data[-period:], ret_lbls[-period:]


def interplate(epochrng, epoch, data) -> tuple:
    """Interpolate the given data to a neat monotonic dataset
    with 10 minute intervals"""
    datarng = np.interp(epochrng, epoch, data)
    return epochrng, datarng


def contract(arr1, arr2):
    """
    Add two arrays together.
    """
    size: int = max(len(arr1), len(arr2))
    rev_arr1 = np.zeros(size, dtype=float)
    rev_arr2 = np.zeros(size, dtype=float)
    for idx in range(0, len(arr1)):
        rev_arr1[idx] = arr1[::-1][idx]
    for idx in range(0, len(arr2)):
        rev_arr2[idx] = arr2[::-1][idx]
    result = np.sum([rev_arr1, rev_arr2], axis=0)
    return result[::-1]


def distract(arr1, arr2, allow_negatives=False):
    """
    Subtract two arrays.
    Note: order is important!

    Args:
        arr1 (numpy.array) : first array
        arr2 (numpy.array) : second array to subtract elementally from the first
        allow_negatives: when False (default), negative results of the subtractions are zeroed.
    """
    size = max(len(arr1), len(arr2))
    rev_arr1 = np.zeros(size, dtype=float)
    rev_arr2 = np.zeros(size, dtype=float)
    for idx in range(0, len(arr1)):
        rev_arr1[idx] = arr1[::-1][idx]
    for idx in range(0, len(arr2)):
        rev_arr2[idx] = arr2[::-1][idx]
    result = np.subtract(rev_arr1, rev_arr2)
    if not allow_negatives:
        result[result < 0] = 0.0
    return result[::-1]


def balance(ilo, ihi, xlo, xhi, own, balans=2) -> tuple:
    """Calculate the balance"""
    import_lo = np.zeros(len(ilo), dtype=float)
    import_hi = np.zeros(len(ihi), dtype=float)
    export_lo = np.zeros(len(xlo), dtype=float)
    export_hi = np.zeros(len(xhi), dtype=float)
    own_usage = np.zeros(len(own), dtype=float)

    if balans == 1:
        # for single balancing we add both meters together
        ilo = contract(ilo, ihi)
        xlo = contract(xlo, xhi)

    diflo = distract(ilo, xlo, allow_negatives=True)
    for idx, value in enumerate(diflo):
        if value >= 0:
            import_lo[idx] = diflo[idx]
            own_usage[idx] = own[idx] + xlo[idx]
            export_lo[idx] = 0.0
        if value < 0:
            import_lo[idx] = 0.0
            own_usage[idx] = own[idx] + ilo[idx]
            export_lo[idx] = abs(diflo[idx])

    if balans == 2:
        # for single balancing we don't need to calculate the hi-meter, as it was
        # previously added tot the lo-meter
        difhi = distract(ihi, xhi, allow_negatives=True)
        for idx, value in enumerate(difhi):
            if value >= 0:
                import_hi[idx] = difhi[idx]
                own_usage[idx] = own[idx] + xhi[idx]
                export_hi[idx] = 0.0
            if value < 0:
                import_hi[idx] = 0.0
                own_usage[idx] = own[idx] + ihi[idx]
                export_hi[idx] = abs(difhi[idx])

    return import_lo, import_hi, export_lo, export_hi, own_usage


def fast_group_data(x_epochs, y_data, grouping, dif=True) -> tuple:
    """A faster version of group_data()."""
    # convert y-values to numpy array
    y_data = np.array(y_data)
    # convert epochs to text
    x_texts = np.array(
        [dt.datetime.fromtimestamp(i).strftime(grouping) for i in x_epochs],
        dtype="str",
    )
    # x_texts =
    # ['12-31 20h' '12-31 21h' '12-31 21h' '12-31 21h' '12-31 21h' '12-31 21h'
    #  '12-31 21h' '12-31 22h' '12-31 22h' '12-31 22h' '12-31 22h' '12-31 22h'
    #  :
    #  '01-01 08h' '01-01 09h' '01-01 09h' '01-01 09h' '01-01 09h' '01-01 09h'
    #  '01-01 09h' '01-01 10h' '01-01 10h' '01-01 10h' '01-01 10h' '01-01 10h'
    #  '01-01 10h']
    y = np.array([0])
    # compress x_texts to a unique list
    # order must be preserved
    _, loc1 = np.unique(x_texts, return_index=True)
    loc_from = np.sort(loc1)
    unique_x_texts = x_texts[loc1]
    loc2 = len(x_texts) - 1 - np.unique(np.flip(x_texts), return_index=True)[1]
    loc_to = np.sort(loc2)

    if not dif:
        # print(y_data)
        # print(loc1, loc2)
        y: list = []
        for i, v in enumerate(loc1):
            # f1 = y_data[v:loc2[i]]
            # print(i, v, loc2[i], f1, f1.sum())
            y.append(y_data[v : loc2[i]].sum())
        y = np.array(y)
    if dif:
        y = y_data[loc_to] - y_data[loc_from]

    returned_y_data = np.where(y > 0, y, 0)

    return unique_x_texts, returned_y_data


def build_arrays44(lbls, use_data, expo_data) -> tuple:
    """Use the input to build two arrays and return them.
    example input line : "2015-01; 329811; 0"  : YYYY-MM; T1; T2
    the list comes ordered by the first field
    the first line and last line can be inspected to find
    the first and last year in the dataset.
    """
    first_year = int(lbls[0].split("-")[0])
    last_year = int(lbls[-1].split("-")[0]) + 1
    num_years = last_year - first_year

    label_lists = [np.arange(first_year, last_year), np.arange(1, 13)]
    usage = np.zeros((num_years, 12))
    exprt = np.zeros((num_years, 12))

    for data_point in zip(lbls, use_data, expo_data):
        [year, month] = data_point[0].split("-")
        col_idx = int(month) - 1
        row_idx = int(year) - first_year
        usage[row_idx][col_idx] = data_point[1]
        exprt[row_idx][col_idx] = data_point[2]
    return label_lists, usage, exprt
