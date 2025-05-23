#!/usr/bin/env python3

# lektrix
# Copyright (C) 2025  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Create trendbargraphs of the energy price data for various periods."""

import argparse
import logging.handlers
import platform
import sys
from datetime import datetime as dt
from datetime import timedelta as dttd

import constants as cs
import libdbqueries as dbq
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

DATABASE: str = cs.PRICES["database"]
TABLE_PRICE: str = cs.PRICES["sql_table"]
DEBUG: bool = False
EDATETIME: str = "'now'"

# Set the display options for pandas to prevent truncating in journal.
pd.set_option("display.max_columns", None)

sys_log = "/dev/log"
if platform.system() == "Darwin":
    sys_log = "/var/run/syslog"
logging.basicConfig(
    level=logging.INFO,
    format="%(module)s.%(funcName)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.handlers.SysLogHandler(
            address=sys_log,
            facility=logging.handlers.SysLogHandler.LOG_DAEMON,
        )
    ],
)
LOGGER: logging.Logger = logging.getLogger(__name__)

# fmt: off
parser = argparse.ArgumentParser(description="Create a trendgraph")
parser.add_argument("--twoday", "-t",
                    action="store_true",
                    help="graph for the last two days"
                    )
# parser.add_argument("--hours", "-hr",
#                     type=int,
#                     help="create hour-trend for last <HOURS> hours",
#                     )
# parser.add_argument("--days", "-d",
#                     type=int,
#                     help="create day-trend for last <DAYS> days"
#                     )
# parser.add_argument("--months", "-m",
#                     type=int,
#                     help="number of months of data to use for the graph",
#                     )
# parser.add_argument("--years", "-y",
#                     type=int,
#                     help="number of months of data to use for the graph",
#                     )
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


class ChunkedLogger:
    """
    A logger wrapper to safely emit large messages or DataFrames in smaller chunks.

    Attributes:
        logger (logging.Logger): The logger instance to use.
        chunk_size (int): Maximum characters per log message for plain text.
        max_lines (int): Maximum lines per log chunk for markdown tables.
    """

    def __init__(
        self, logger: logging.Logger, chunk_size: int = 1000, max_lines: int = 5
    ) -> None:
        """
        Initialize the ChunkedLogger.

        Args:
            logger (logging.Logger): Standard Python logger.
            chunk_size (int): Max characters per log message (default: 1000).
            max_lines (int): Max lines per log chunk for markdown tables (default: 50).
        """
        self.logger = logger
        self.chunk_size = chunk_size
        self.max_lines = max_lines

    def log(self, level: int, message: str) -> None:
        """
        Log a long plain-text message in chunks.

        Args:
            level (int): Logging level (e.g., logging.INFO).
            message (str): The message to log.
        """
        if not isinstance(message, str):
            raise ValueError("Message must be a string.")
        if not isinstance(level, int) or level not in logging._levelToName:
            raise ValueError("Invalid logging level.")

        for i in range(0, len(message), self.chunk_size):
            self.logger.log(level, message[i : i + self.chunk_size])

    def log_df(
        self, df: pd.DataFrame, level: int = logging.INFO, line_safe: bool = True, **kwargs
    ) -> None:
        """
        Log a DataFrame as markdown in safe-size chunks.

        Args:
            df (pd.DataFrame): The DataFrame to log.
            level (int): Logging level (default: logging.INFO).
            line_safe (bool): If True, chunk by line count. If False, chunk by char length.
            kwargs: Additional arguments passed to `df.to_markdown()`.
        """
        if df.empty:
            self.logger.log(level, "DataFrame is empty.")
            return

        try:
            md = df.to_markdown(**kwargs)
        except Exception as e:
            self.logger.error(f"Failed to convert DataFrame to markdown: {e}")
            return

        if line_safe:
            lines: list = ["\n"]
            lines += md.splitlines()
            for i in range(0, len(lines), self.max_lines):
                chunk = "\n".join(lines[i : i + self.max_lines])
                self.logger.log(level, chunk)
        else:
            self.log(level, md)


def fetch_data(hours_to_fetch: int = 48, aggregation: str = "H") -> dict:
    """Query the database to fetch the requested data

    Args:
        hours_to_fetch (int): hours of data to retrieve
        aggregation (str): pandas resample rule

    Returns:
        dict with dataframes containing mains and production data
    """
    # Use a chuncking logger to avoid sending too much text to syslog
    chunked_logger = ChunkedLogger(LOGGER)
    settings = {
        "debug": OPTION.debug,
        "edatetime": EDATETIME,
        "table": "",
        "database": DATABASE,
        "hours_to_fetch": hours_to_fetch - 2,  # compensate for greedy query
        "aggregation": aggregation,
        "parse_dates": ["sample_time"],
        "index_col": "sample_epoch",
        "cols2drop": [],
        "median": False,
        "minimum": False,
        # "bar_colors": ["red", "seagreen", "orange"],
    }
    LOGGER.debug(f"\nRequest {hours_to_fetch} hours of price data")
    settings["table"] = TABLE_PRICE
    settings["cols2drop"] = ["site_id"]
    df = dbq.pass1_process_prices(dbq.query_for_data(settings=settings), settings, 1)
    df = df.sort_index(axis=1)

    df = dbq.separate_prices(df, settings)

    LOGGER.debug("\n\no  database concatenated data")
    chunked_logger.log_df(df, floatfmt=".3f", level=logging.DEBUG)
    LOGGER.debug("\n======\n\n")

    data_dict = {
        "prices": df,
    }

    return data_dict


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
    # if opt.days:
    #     plot_graph(
    #         output_file=cs.PRICES["day_graph"],
    #         data_dict=fetch_data(hours_to_fetch=opt.days * 24, aggregation="D"),
    #         plot_title=f" trend afgelopen dagen ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
    #         locatorformat=["day", "%Y-%m-%d"],
    #     )
    # if opt.months:
    #     plot_graph(
    #         output_file=cs.PRICES["month_graph"],
    #         data_dict=fetch_data(hours_to_fetch=opt.months * 31 * 24, aggregation="M"),
    #         plot_title=f" trend afgelopen maanden ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
    #         show_data=False,
    #         locatorformat=["month", "%Y-%m"],
    #     )
    # if opt.years:
    #     plot_graph(
    #         output_file=cs.PRICES["year_graph"],
    #         data_dict=fetch_data(hours_to_fetch=opt.years * 366 * 24, aggregation="A"),
    #         plot_title=f" trend afgelopen jaren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
    #         show_data=True,
    #         locatorformat=["year", "%Y"],
    #     )


if __name__ == "__main__":
    print(f"Trending (price) with Python {sys.version}")
    if OPTION.twoday:
        # ATTENTION: the calculation of average prices depends on there being a
        # whole number of days in the period
        edate = dt.now().replace(hour=23, minute=0, second=0, microsecond=0) + dttd(days=1)
        EDATETIME = f"'{dt.strftime(edate, cs.DT_FORMAT)}'"
        sdate = dt.now().replace(hour=0, minute=0, second=0, microsecond=0)
        OPTION.hours = (edate - sdate).total_seconds() / 3600
    # if OPTION.hours == 0:
    #     edate = dt.now().replace(hour=23, minute=0, second=0, microsecond=0) + dttd(days=1)
    #     EDATETIME = f"'{dt.strftime(edate, cs.DT_FORMAT)}'"
    #     OPTION.hours = 8 * 24
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
