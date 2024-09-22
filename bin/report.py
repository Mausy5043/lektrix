#!/usr/bin/env python3

"""Create a report of the data for a given period.
Using kamstrup data
"""

# pylint: disable=C0413
import argparse
import sqlite3 as s3
from datetime import datetime as dt

import constants
import pandas as pd

DATABASE: str = constants.TREND["database"]
TABLE_MAINS: str = constants.KAMSTRUP["sql_table"]
TABLE_PRDCT: str = constants.SOLAREDGE["sql_table"]
TABLE_CHRGR: str = constants.ZAPPI["sql_table"]
DEBUG: bool = False

# fmt:off
parser = argparse.ArgumentParser(description="Create a report")
parser.add_argument("--hours", "-hr",
                    type=int,
                    help="create hour-trend for last <HOURS> hours",
                    )
parser.add_argument("--days", "-d",
                    type=int,
                    help="create day-trend for last <DAYS> days"
                    )
parser.add_argument("--months", "-m",
                    type=int,
                    help="number of months of data to use for the graph",
                    )
parser.add_argument("--years", "-y",
                    type=int,
                    help="number of months of data to use for the graph",
                    )
parser_group = parser.add_mutually_exclusive_group(required=False)
parser_group.add_argument("--debug",
                          action="store_true",
                          help="start in debugging mode"
                          )
OPTION = parser.parse_args()
# fmt: on


def fetch_data(hours_to_fetch=48, aggregation="W") -> dict:
    """
    Query the database to fetch the requested data

    Args:
        hours_to_fetch (int): hours of data to retrieve
        aggregation (str): pandas resample rule

    Returns:
        dict with dataframes containing mains and production data
    """
    if DEBUG:
        print("\nRequest data from mains")
    df_mains = fetch_data_mains(hours_to_fetch=hours_to_fetch, aggregation=aggregation)
    if DEBUG:
        print("\nRequest data from production")
    df_prod = fetch_data_production(hours_to_fetch=hours_to_fetch, aggregation=aggregation)
    data_dict = {}

    # Add production data then calculate self-use by extracting exported amount
    try:
        df_mains.insert(2, "EB", df_prod["energy"])
        df_mains.insert(3, "Solar", df_prod["energy"])
    except KeyError:
        df_mains.insert(2, "EB", 0)
    df_mains["EB"] += df_mains["T1out"] + df_mains["T2out"]  # T1out and T2out are (-)-ve values !
    df_mains.insert(2, "TotalExport", 0)
    df_mains["TotalExport"] += df_mains["T1out"] + df_mains["T2out"]
    df_mains.insert(2, "TotalImport", 0)
    df_mains["TotalImport"] += df_mains["T1in"] + df_mains["T2in"]
    df_mains.insert(2, "Usage", 0)
    df_mains["Usage"] += df_mains["EB"] + df_mains["TotalImport"]
    df_mains.insert(2, "Balance", 0)
    df_mains["Balance"] += df_mains["TotalExport"] + df_mains["TotalImport"]

    # put columns in the right order for plotting
    # fmt: off
    categories = ["T1out", "T2out", "TotalExport", "T1in", "T2in", "TotalImport", "Usage", "EB", "Solar", "Balance"]
    # fmt: on
    df_mains.columns = pd.CategoricalIndex(
        df_mains.columns.values, ordered=True, categories=categories
    )
    df_mains = df_mains.sort_index(axis=1)
    if DEBUG:
        print("\n\n  ** MAINS data for plotting ** ")
        print(df_mains.to_markdown(floatfmt=".3f"))

        print("\n\n  ** PRODUCTION data for plotting ** ")
        print(df_prod.to_markdown(floatfmt=".3f"))
    data_dict["mains"] = df_mains
    # data_dict["production"] = df_prod
    return data_dict


def fetch_data_mains(hours_to_fetch=48, aggregation="H") -> pd.DataFrame:
    """
    Query the database to fetch the requested data

    Args:
        hours_to_fetch (int):      number of hours of data to fetch
        aggregation (str):         pandas resample rule

    Returns:
        pandas.DataFrame() with data
    """
    if DEBUG:
        print("\n*** fetching MAINS data ***")

    mod_start: str = ""
    # aggregations = "HDMA"
    # mods = ["hour", "day", "month", "year"]
    # mod_start = f", 'start of {mods[aggregations.index(aggregation)]}'"

    where_condition: str = (
        f" (sample_time >= datetime('now', '-{hours_to_fetch + 1} hours'{mod_start}))"
    )
    group_condition: str = ""
    if aggregation == "H":
        group_condition = "GROUP BY strftime('%Y-%m-%d %H', sample_time)"
    s3_query: str = (
        f"SELECT * "  # nosec B608
        f"FROM {TABLE_MAINS} "
        f"WHERE {where_condition} {group_condition};"
    )
    if DEBUG:
        print(s3_query)

    # Get the data
    with s3.connect(DATABASE) as con:
        df: pd.DataFrame = pd.read_sql_query(
            s3_query, con, parse_dates=["sample_time"], index_col="sample_epoch"
        )
    if DEBUG:
        print("o  database mains data")
        print(df)

    # Pre-processing
    # drop sample_time separately!
    df.drop("sample_time", axis=1, inplace=True, errors="ignore")
    df.drop(["powerin", "powerout", "tarif", "swits"], axis=1, inplace=True, errors="ignore")

    for c in df.columns:
        if c not in ["sample_time"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df.index = pd.to_datetime(df.index, unit="s")  # noqa
    # resample to monotonic timeline
    df = df.resample(f"{aggregation}").max()

    df = df.diff()  # KAMSTRUP data contains totalisers, we need the differential per timeframe
    df["T1in"] *= 0.001  # -> kWh import
    df["T2in"] *= 0.001  # -> kWh import
    df["T1out"] *= -0.001  # -> kWh export
    df["T2out"] *= -0.001  # -> kWh export

    # drop first row as it will usually not contain valid or complete data
    df = df.iloc[1:, :]

    if DEBUG:
        print("o  database mains data pre-processed")
        print(df)
    return df


def fetch_data_production(hours_to_fetch=48, aggregation="H") -> pd.DataFrame:
    """
    Query the database to fetch the requested data

    Args:
        hours_to_fetch (int):      number of hours of data to fetch
        aggregation (str):         pandas resample rule

    Returns:
        pandas.DataFrame() with data
    """
    if DEBUG:
        print("\n*** fetching PRODUCTION data ***")

    mod_start = ""
    # aggregations = "HDMA"
    # mods = ["hour", "day", "month", "year"]
    # mod_start = f", 'start of {mods[aggregations.index(aggregation)]}'"

    where_condition: str = (
        f" (sample_time >= datetime('now', '-{hours_to_fetch + 1} hours'{mod_start}))"
    )
    s3_query: str = (
        f"SELECT * "  # nosec B608
        f"FROM {TABLE_PRDCT} "
        f"WHERE {where_condition}"
    )
    if DEBUG:
        print(s3_query)

    # Get the data
    with s3.connect(DATABASE) as con:
        df = pd.read_sql_query(
            s3_query, con, parse_dates=["sample_time"], index_col="sample_epoch"
        )
    if DEBUG:
        print("o  database production data")
        print(df)

    # Pre-processing
    # drop sample_time separately!
    df.drop("sample_time", axis=1, inplace=True, errors="ignore")
    df.drop("site_id", axis=1, inplace=True, errors="ignore")

    for c in df.columns:
        if c not in ["sample_time"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # df.index = pd.to_datetime(df.index, unit='s')
    #            .tz_localize("UTC")
    #            .tz_convert("Europe/Amsterdam")
    df.index = pd.to_datetime(df.index, unit="s")  # noqa

    # resample to monotonic timeline
    lbl = "right"
    if aggregation == "D":
        lbl = "left"
    df = df.resample(f"{aggregation}", label=lbl).sum()

    df["energy"] *= 0.001  # -> kWh

    # drop first row as it will usually not contain valid data
    # df = df.iloc[1:, :]

    if DEBUG:
        print("o  database production data pre-processed")
        print(df)
    return df


def report(data_dict) -> None:
    """Report the data in a textfile.

    Args:
        data_dict (dict): dict containing the datasets to be plotted

    Returns: nothing
    """

    print("\n\n*** REPORTING ***")
    for parameter in data_dict:
        data_frame = data_dict[parameter]  # type: pd.DataFrame
        print(parameter)
        sums = data_frame.sum().rename("total")
        # we use to_string() here to prevent pandas compressing the output when
        # redirecting to pipe
        print(data_frame.to_string())
        print("\nTotals for reported period")
        print(sums.to_string())
        print("\nBalance this period:")
        print(int(sums["TotalImport"] + sums["TotalExport"]))


def main(opt) -> None:
    """
    This is the main loop
    """
    if opt.hours:
        report(
            fetch_data(hours_to_fetch=opt.hours, aggregation="h"),
        )
    if opt.days:
        report(
            fetch_data(hours_to_fetch=opt.days * 24, aggregation="D"),
        )
    if opt.months:
        report(
            fetch_data(hours_to_fetch=opt.months * 31 * 24, aggregation="ME"),
        )
    if opt.years:
        report(
            fetch_data(hours_to_fetch=opt.years * 366 * 24, aggregation="YE"),
        )


if __name__ == "__main__":
    if OPTION.hours == 0:
        OPTION.hours = 80
    if OPTION.days == 0:
        OPTION.days = 80
    if OPTION.months == 0:
        OPTION.months = 6 * 12 + dt.now().month
    if OPTION.years == 0:
        OPTION.years = 10

    if OPTION.debug:
        print(OPTION)
        DEBUG = True
        print("DEBUG-mode started")
    main(OPTION)
