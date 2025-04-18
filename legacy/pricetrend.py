#!/usr/bin/env python3

# lektrix
# Copyright (C) 2024  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

"""Create trendbargraphs of the data for various periods.
Using pricing data
"""

import argparse
import random
import sqlite3 as s3
import sys
import time
from datetime import datetime as dt
from datetime import timedelta as dttd

import constants as cs
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

DATABASE = cs.PRICES["database"]
TABLE_PRICE = cs.PRICES["sql_table"]
DEBUG = False
EDATETIME = "'now'"

# fmt: off
parser = argparse.ArgumentParser(description="Create a trendgraph")
parser.add_argument("--twoday", "-t",
                    action="store_true",
                    help="graph for the last two days"
                    )
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
parser.add_argument("--edate", "-e",
                    type=str,
                    help="date of last day of the graph (default: now)",
                    )
parser_group = parser.add_mutually_exclusive_group(required=False)
parser_group.add_argument("--debug",
                          action="store_true",
                          help="start in debugging mode"
                          )
OPTION = parser.parse_args()
# fmt: on


def fetch_data(hours_to_fetch=48, aggregation="H") -> dict:
    """Query the database to fetch the requested data

    Args:
        hours_to_fetch (int): hours of data to retrieve
        aggregation (str): pandas resample rule

    Returns:
        dict with dataframe containing the data
    """
    if DEBUG:
        print(f"\nRequest {hours_to_fetch} hours of pricing data")
    df_price = fetch_data_prices(hours_to_fetch=hours_to_fetch, aggregation=aggregation)

    df_price = df_price.sort_index(axis=1)
    if DEBUG:
        print("\n\n ** PRICING data for plotting  **")
        print(df_price.to_markdown(floatfmt=".3f"))

    data_dict: dict = {}
    data_dict["prices"] = df_price
    return data_dict


def fetch_data_prices(hours_to_fetch=48, aggregation="H") -> pd.DataFrame:
    """Query the database to fetch the requested data

    Args:
        hours_to_fetch (int):      number of hours of data to fetch
        aggregation (str):         pandas resample rule

    Returns:
        pandas.DataFrame() with data
    """
    df = pd.DataFrame()
    if DEBUG:
        print("\n*** fetching PRICING data ***")

    where_condition = (
        f" ( sample_time >= datetime({EDATETIME}, '-{hours_to_fetch} hours')"
        f" AND sample_time <= datetime({EDATETIME}, '+1 hours') )"
    )
    group_condition = ""
    # if aggregation == 'H':
    #     group_condition = "GROUP BY strftime('%d %H', sample_time)"
    s3_query: str = (
        f"SELECT * "  # nosec B608
        f"FROM {TABLE_PRICE} "
        f"WHERE {where_condition} {group_condition};"
    )
    if DEBUG:
        print(s3_query)

    # Get the data
    success = False
    retries = 5
    while not success and retries > 0:
        try:
            with s3.connect(DATABASE) as con:
                df = pd.read_sql_query(
                    s3_query, con, parse_dates=["sample_time"], index_col="sample_epoch"
                )
                success = True
        except (s3.OperationalError, pd.errors.DatabaseError) as exc:
            if DEBUG:
                print("Database may be locked. Waiting...")
            retries -= 1
            time.sleep(random.randint(30, 60))  # nosec: B311
            if retries == 0:
                raise TimeoutError("Database seems locked.") from exc

    if DEBUG:
        print("\no  database pricing data")
        print(df.to_markdown(floatfmt=".5f"))

    # Pre-processing
    # daily averages
    davg_df = df.groupby(pd.Grouper(freq="D", key="sample_time")).mean()
    # print(davg_df.to_markdown(floatfmt=".5f"))
    _l: list = []
    for row in range(len(davg_df)):
        day_avg = davg_df.iloc[row]["price"]
        _l += [day_avg] * 24
    df["avg_price"] = _l
    df["past"] = np.where(df["sample_time"] < dt.now(), df["price"], np.nan)
    df["low"] = np.where(df["price"] <= df["avg_price"], df["price"], np.nan)
    df["low"] = np.where(df["past"].notna(), np.nan, df["low"])
    df["high"] = np.where(df["price"] > df["avg_price"], df["price"], np.nan)
    df["high"] = np.where(df["past"].notna(), np.nan, df["high"])

    # drop sample_time separately!
    df.drop("sample_time", axis=1, inplace=True, errors="ignore")

    df.drop(["avg_price", "price"], axis=1, inplace=True, errors="ignore")

    for c in df.columns:
        if c not in ["sample_time"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df.index = pd.to_datetime(df.index, unit="s")  # noqa

    if DEBUG:
        print("\no  database pricing data pre-processed")
        print(df.to_markdown(floatfmt=".5f"))
    return df


def compute_avg_val(df):
    df["average"] = df["price"].mean()
    return df


def plot_graph(output_file, data_dict, plot_title, show_data=False, locatorformat=None) -> None:
    """Plot the data in a chart.

    Args:
        output_file (str): path & filestub of the resulting plot.
                           The parametername will be appended as will the
                           extension .png.
        data_dict (dict): dict containing the datasets to be plotted
        plot_title (str): text for the title to be placed above the plot
        show_data (bool): whether to show numerical values in the plot.
        locatorformat (list): formatting information for xticks

    Returns: nothing
    """
    if locatorformat is None:
        # locatorformat = ["hour", "%d-%m %Hh"]
        locatorformat = ["hour", "%Hh"]
    if DEBUG:
        print("\n\n*** PLOTTING ***")
    for parameter in data_dict:
        data_frame = data_dict[parameter]  # type: pd.DataFrame
        if DEBUG:
            print(parameter)
            print(data_frame.to_markdown(floatfmt=".3f"))
        mjr_ticks = int(len(data_frame.index) / 40)
        if mjr_ticks <= 0:
            mjr_ticks = 1
        ticklabels = [""] * len(data_frame.index)
        ticklabels[::mjr_ticks] = [
            item.strftime(locatorformat[1]) for item in data_frame.index[::mjr_ticks]
        ]
        if DEBUG:
            print(ticklabels)
        if len(data_frame.index) == 0:
            if DEBUG:
                print("No data.")
        else:
            fig_x = 20
            fig_y = 7.5
            fig_fontsize = 13
            ahpla = 0.7

            # create a line plot
            plt.rc("font", size=fig_fontsize)
            ax1 = data_frame.plot(
                kind="bar",
                stacked=True,
                width=0.9,
                figsize=(fig_x, fig_y),
                color=["red", "seagreen", "orange"],
            )
            # linewidth and alpha need to be set separately
            for _, a in enumerate(ax1.lines):
                plt.setp(a, alpha=ahpla, linewidth=1, linestyle=" ")
            if show_data:
                x_offset = -0.1
                for p in ax1.patches:
                    b = p.get_bbox()  # type: ignore[attr-defined]
                    val = f"{b.y1 - b.y0:{cs.FLOAT_FMT}}"
                    ax1.annotate(
                        val,
                        ((b.x0 + b.x1) / 2 + x_offset, b.y0 + 0.5 * (b.y1 - b.y0)),
                        rotation=30,
                    )
            ax1.set_ylabel(parameter)
            ax1.legend(loc="upper left", ncol=8, framealpha=0.2)
            ax1.set_xlabel("Datetime")
            ax1.grid(which="major", axis="y", color="k", linestyle="--", linewidth=0.5)
            ax1.xaxis.set_major_formatter(mticker.FixedFormatter(ticklabels))
            plt.gcf().autofmt_xdate()
            plt.title(f"{parameter} {plot_title}")
            plt.tight_layout()
            plt.savefig(fname=f"{output_file}_{parameter}.png", format="png")
            if DEBUG:
                print(f" --> {output_file}_{parameter}.png\n")


def main(opt) -> None:
    """
    This is the main loop
    """
    if opt.hours:
        plot_graph(
            output_file=cs.PRICES["hour_graph"],
            data_dict=fetch_data(hours_to_fetch=opt.hours, aggregation="H"),
            plot_title=f" trend afgelopen uren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            locatorformat=["hour", "%Hh"],
        )
    if opt.days:
        plot_graph(
            output_file=cs.PRICES["day_graph"],
            data_dict=fetch_data(hours_to_fetch=opt.days * 24, aggregation="D"),
            plot_title=f" trend afgelopen dagen ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            locatorformat=["day", "%Y-%m-%d"],
        )
    if opt.months:
        plot_graph(
            output_file=cs.PRICES["month_graph"],
            data_dict=fetch_data(hours_to_fetch=opt.months * 31 * 24, aggregation="M"),
            plot_title=f" trend afgelopen maanden ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            show_data=False,
            locatorformat=["month", "%Y-%m"],
        )
    if opt.years:
        plot_graph(
            output_file=cs.PRICES["year_graph"],
            data_dict=fetch_data(hours_to_fetch=opt.years * 366 * 24, aggregation="A"),
            plot_title=f" trend afgelopen jaren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            show_data=True,
            locatorformat=["year", "%Y"],
        )


if __name__ == "__main__":
    print(f"Trending (price) with Python {sys.version}")
    if OPTION.twoday:
        # ATTENTION: the calculation of average prices depends on there being a
        # whole number of days in the period
        edate = dt.now().replace(hour=23, minute=0, second=0, microsecond=0) + dttd(days=1)
        EDATETIME = f"'{dt.strftime(edate, cs.DT_FORMAT)}'"
        sdate = dt.now().replace(hour=0, minute=0, second=0, microsecond=0)
        OPTION.hours = (edate - sdate).total_seconds() / 3600
    if OPTION.hours == 0:
        edate = dt.now().replace(hour=23, minute=0, second=0, microsecond=0) + dttd(days=1)
        EDATETIME = f"'{dt.strftime(edate, cs.DT_FORMAT)}'"
        OPTION.hours = 8 * 24
    # if OPTION.days == 0:
    #     edate = dt.now().replace(hour=23, minute=0, second=0, microsecond=0) + dttd(days=1)
    #     EDATETIME = f"'{dt.strftime(edate, cs.DT_FORMAT)}'"
    #     OPTION.days = 80
    # if OPTION.months == 0:
    #     edate = dt.now().replace(hour=23, minute=0, second=0, microsecond=0) + dttd(days=1)
    #     EDATETIME = f"'{dt.strftime(edate, cs.DT_FORMAT)}'"
    #     OPTION.months = 6 * 12 + dt.now().month
    # if OPTION.years == 0:
    #     edate = dt.now().replace(hour=23, minute=0, second=0, microsecond=0) + dttd(days=1)
    #     EDATETIME = f"'{dt.strftime(edate, cs.DT_FORMAT)}'"
    #     OPTION.years = 10
    if OPTION.edate:
        print("NOT NOW")
        EDATETIME = f"'{OPTION.edate}'"

    if OPTION.debug:
        print(OPTION)
        DEBUG = True
        print("DEBUG-mode started")
    main(OPTION)
