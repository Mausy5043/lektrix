#!/usr/bin/env python3

"""Create trendbargraphs of the data for various periods.
Using myenergi data
"""

# FIXME: still needs work

import argparse
import sqlite3 as s3
import warnings
from datetime import datetime as dt

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

import constants

warnings.simplefilter(action="ignore", category=FutureWarning)

DATABASE = constants.TREND["database"]
TABLE_MAINS = constants.KAMSTRUP["sql_table"]
TABLE_PRDCT = constants.SOLAREDGE["sql_table"]
TABLE_CHRGR = constants.ZAPPI["sql_table"]
OPTION = ""
DEBUG = False


def fetch_data(hours_to_fetch=48, aggregation="W"):
    """Query the database to fetch the requested data

    Args:
        hours_to_fetch (int): hours of data to retrieve
        aggregation (str): pandas resample rule

    Returns:
        dict with dataframes containing mains and production data
    """
    if DEBUG:
        print("\nRequest data from charger")
    df_chrg = fetch_data_charger(hours_to_fetch=hours_to_fetch, aggregation=aggregation)

    # rename rows and perform calculations
    # EVnet := h1b(+)
    # EVsol := h1d(+)
    # import := imp(+) - EVnet
    # export := exp(-)
    # EB := gep(+) + export - EVsol

    # imported and used for EV
    df_chrg["EVnet"] = df_chrg["h1b"]
    # solar used for EV
    df_chrg["EVsol"] = df_chrg["h1d"]
    # compensate for import diverted to EV ...
    df_chrg["import"] = df_chrg["imp"] - df_chrg["EVnet"]
    # ... and/or import
    df_chrg["export"] = df_chrg["exp"]
    # compensate for solar diverted to EV ...
    df_chrg["EB"] = df_chrg["gep"] + df_chrg["export"] - df_chrg["EVsol"]
    # ... and/or export ('export' is negative!)
    df_chrg["EB"][df_chrg["EB"] < 0] = 0

    # 'gen' is energy consumed by solar (operational power to converter) mainly at night.
    # TODO: 'gen' is currently disregarded
    df_chrg.drop(
        ["h1b", "h1d", "gen", "imp", "exp", "gep"],
        axis=1,
        inplace=True,
        errors="ignore",
    )

    # put columns in the right order for plotting
    categories = ["export", "EB", "EVsol", "EVnet", "import"]
    df_chrg.columns = pd.CategoricalIndex(
        df_chrg.columns.values, ordered=True, categories=categories
    )
    df_chrg = df_chrg.sort_index(axis=1)
    if DEBUG:
        print("\n\n ** CHARGER data for plotting  **")
        print(df_chrg.to_markdown(floatfmt=".3f"))

    data_dict = {}
    data_dict["charger"] = df_chrg
    return data_dict


def fetch_data_charger(hours_to_fetch=48, aggregation="H"):
    """Query the database to fetch the requested data

    Args:
        hours_to_fetch (int):      number of hours of data to fetch
        aggregation (str):         pandas resample rule

    Returns:
        pandas.DataFrame() with data
    """
    if DEBUG:
        print("\n*** fetching CHARGER data ***")

    mod_start = ""
    # aggregations = "HDMA"
    # mods = ["hour", "day", "month", "year"]
    # mod_start = f", 'start of {mods[aggregations.index(aggregation)]}'"

    where_condition = (
        f" (sample_time >= datetime('now'," f" '-{hours_to_fetch + 1} hours'{mod_start}))"
    )
    group_condition = ""
    # if aggregation == 'H':
    #     group_condition = "GROUP BY strftime('%d %H', sample_time)"
    s3_query = f"SELECT * FROM {TABLE_CHRGR} WHERE {where_condition} {group_condition};"
    if DEBUG:
        print(s3_query)

    # Get the data
    with s3.connect(DATABASE) as con:
        df = pd.read_sql_query(s3_query, con, parse_dates="sample_time", index_col="sample_epoch")

    # convert Joules to kWh
    J_to_kWh = 1 / (60 * 60 * 1000)
    df["exp"] *= -1 * J_to_kWh  # -> kWh export
    df["imp"] *= J_to_kWh  # -> kWh import
    df["gen"] *= -1 * J_to_kWh  # -> kWh storage charge
    df["gep"] *= J_to_kWh  # -> kWh solar production or storage discharge
    df["h1b"] *= J_to_kWh  # -> kWh import to EV
    df["h1d"] *= J_to_kWh  # -> kWh solar production to EV

    # Sometimes (especially at the end of an early morning charge) `h1d` will be > 0
    # even when `gep` == 0. It seems power is leaking from `h1b` to `h1d`.
    # Let's correct for that anomaly here:
    leak = pd.DataFrame(index=df.index)
    leak["h1d-gep"] = df["h1d"] - df["gep"]
    leak["h1d-gep"][leak["h1d-gep"] < 0] = 0
    df["h1d"] -= leak["h1d-gep"]
    df["h1b"] += leak["h1d-gep"]

    if DEBUG:
        print("o  database charger data")
        print(df.to_markdown(floatfmt=".3f"))

    # Pre-processing
    # drop sample_time separately!
    df.drop("sample_time", axis=1, inplace=True, errors="ignore")
    df.drop(["site_id", "v1", "frq"], axis=1, inplace=True, errors="ignore")

    for c in df.columns:
        if c not in ["sample_time"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # df.index = pd.to_datetime(df.index, unit='s')
    #              .tz_localize("UTC")
    #              .tz_convert("Europe/Amsterdam")
    df.index = pd.to_datetime(df.index, unit="s")  # noqa

    # resample to monotonic timeline
    df = df.resample(f"{aggregation}").sum()

    # drop first row as it will usually not contain valid or complete data
    df = df.iloc[1:, :]

    if DEBUG:
        print("o  database charger data pre-processed")
        print(df.to_markdown(floatfmt=".3f"))
    return df


def remove_nans(frame, col_name, default):
    """remove NANs from a series"""
    for idx, tmpr in enumerate(frame[col_name]):
        if np.isnan(tmpr):
            if idx == 0:
                frame.at[idx, col_name] = default
            else:
                frame.at[idx, col_name] = frame.at[idx - 1, col_name]
    return frame


def plot_graph(output_file, data_dict, plot_title, show_data=False, locatorformat=None):
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
        locatorformat = ["hour", "%d-%m %Hh"]
    if DEBUG:
        print("\n\n*** PLOTTING ***")
    for parameter in data_dict:
        data_frame = data_dict[parameter]  # type: pd.DataFrame
        # if DEBUG:
        #     print(parameter)
        #     print(data_frame)
        mjr_ticks = int(len(data_frame.index) / 30)
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
                color=["blue", "seagreen", "lightgreen", "salmon", "red"],
            )
            # linewidth and alpha need to be set separately
            for _, l in enumerate(ax1.lines):
                plt.setp(l, alpha=ahpla, linewidth=1, linestyle=" ")
            if show_data:
                x_offset = -0.1
                for p in ax1.patches:
                    b = p.get_bbox()
                    val = f"{b.y1 - b.y0:{constants.FLOAT_FMT}}"
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


def main():
    """
    This is the main loop
    """
    if OPTION.hours:
        plot_graph(
            constants.TREND["hour_graph_v2"],
            fetch_data(hours_to_fetch=OPTION.hours, aggregation="H"),
            f" trend afgelopen uren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            locatorformat=["hour", "%d-%m %Hh"],
        )
    if OPTION.days:
        plot_graph(
            constants.TREND["day_graph_v2"],
            fetch_data(hours_to_fetch=OPTION.days * 24, aggregation="D"),
            f" trend afgelopen dagen ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            locatorformat=["day", "%Y-%m-%d"],
        )
    if OPTION.months:
        plot_graph(
            constants.TREND["month_graph_v2"],
            fetch_data(hours_to_fetch=OPTION.months * 31 * 24, aggregation="M"),
            f" trend afgelopen maanden ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            show_data=True,
            locatorformat=["month", "%Y-%m"],
        )
    if OPTION.years:
        plot_graph(
            constants.TREND["year_graph_v2"],
            fetch_data(hours_to_fetch=OPTION.years * 366 * 24, aggregation="A"),
            f" trend afgelopen jaren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            show_data=True,
            locatorformat=["year", "%Y"],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a trendgraph")
    # fmt: off
    parser.add_argument("-hr",
                        "--hours",
                        type=int,
                        help="create hour-trend for last <HOURS> hours",
    )
    parser.add_argument("-d",
                        "--days",
                        type=int,
                        help="create day-trend for last <DAYS> days")
    parser.add_argument("-m",
                        "--months",
                        type=int,
                        help="number of months of data to use for the graph",
    )
    parser.add_argument("-y",
                        "--years",
                        type=int,
                        help="number of months of data to use for the graph",
    )
    parser_group = parser.add_mutually_exclusive_group(required=False)
    parser_group.add_argument("--debug",
                              action="store_true",
                              help="start in debugging mode"
                              )
    OPTION = parser.parse_args()  # type: ignore
    # fmt: on
    if OPTION.hours == 0:
        OPTION.hours = 80
    if OPTION.days == 0:
        OPTION.days = 80
    if OPTION.months == 0:
        OPTION.months = 38
    if OPTION.years == 0:
        OPTION.years = 12

    if OPTION.debug:
        print(OPTION)
        DEBUG = True
        print("DEBUG-mode started")
    main()
