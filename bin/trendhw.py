#!/usr/bin/env python3

# lektrix
# Copyright (C) 2024  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

"""Create trendbargraphs of the data for various periods.
Using myenergi data
"""

# pylint: disable=C0413
import argparse
import logging.handlers
import platform
import sys
import warnings
from datetime import datetime as dt

import constants as cs
import libdbqueries as dbq
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

# FutureWarning: The default value of numeric_only in DataFrameGroupBy.sum is deprecated.
# In a future version, numeric_only will default to False. Either specify numeric_only or
# select only columns which should be valid for the function.
#   df = df.resample(f"{aggregation}", label=lbl).sum()
warnings.simplefilter(action="ignore", category=FutureWarning)

DATABASE: str = cs.TREND["database"]
TABLE_MAINS: str = cs.WIZ_KWH["sql_table"]
TABLE_PRDCT: str = cs.SOLAREDGE["sql_table"]
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
            lines = md.splitlines()
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
        "debug": DEBUG,
        "edatetime": EDATETIME,
        "table": "",
        "database": DATABASE,
        "hours_to_fetch": hours_to_fetch,
        "aggregation": aggregation,
        "parse_dates": ["sample_time"],
        "index_col": "sample_epoch",
        "cols2drop": [],
    }
    LOGGER.debug(f"\nRequest {hours_to_fetch} hours of MAINS data")
    settings["table"] = TABLE_MAINS
    settings["cols2drop"] = ["site_id", "v1", "frq"]
    df_mains = dbq.post_process_mains(dbq.query_for_data(settings=settings), settings)
    df_mains_len = df_mains.shape[0]

    LOGGER.debug(f"\nRequest {hours_to_fetch} hours of PRODUCTION data")
    settings["table"] = TABLE_PRDCT
    settings["cols2drop"] = ["site_id"]
    df_prod = dbq.post_process_production(
        dbq.query_for_data(settings=settings), settings, df_mains_len
    )

    LOGGER.debug(f"\nRequest {hours_to_fetch} hours of price data")
    settings["table"] = TABLE_PRICE
    settings["cols2drop"] = ["site_id"]
    df_pris = dbq.post_process_prices(
        dbq.query_for_data(settings=settings), settings, df_mains_len
    )
    # merge the dataframes
    # join='outer': This is the default option. It performs a union of the indexes,
    #               including all indexes from all DataFrames.
    #               Missing values will be filled with NaN.
    # join='inner': This option performs an intersection of the indexes, including
    #               only the indexes that are present in all DataFrames. This results
    #               in a DataFrame that contains only the common indexes.
    df = pd.concat([df_mains, df_prod, df_pris], axis="columns", join="inner")
    LOGGER.debug("\n\no  database concatenated data")
    chunked_logger.log_df(df, floatfmt=".3f", level=logging.DEBUG)
    LOGGER.debug("\n======\n\n")

    # rename rows and perform calculations
    # exp: exported to grid
    # imp: imported from grid to home
    # gen: consumed by PV (feeding to battery)
    # gep: generated by PV to home (solar production or delivered from battery)
    # evn: consumed by EV
    # evp: V2H from EV to home
    # solar: solar production
    # price: price of energy in the timeperiod
    # own: home usage from PV or V2H := gep + evp + exp
    #
    # (temp) total EV usage
    df["EVtotal"] = df["evp"] + df["evn"]
    # (temp) total SOLAR
    df["PVtotal"] = df["gen"] + df["gep"]
    # (temp) total P1
    df["P1total"] = df["imp"] + df["exp"]
    # 'own' is the total energy used internally by the home (was: eigen bedrijf; EB).
    # that is: *not* imported from the grid
    # NOTE that 'gen' and 'evn' are not used in the calculation of 'own'
    # because they are diverted from somewhere else (one of the __p values)
    df["own"] = df["exp"] + df["gep"] + df["evp"]
    # any negative 'own' is set to zero, because there are no other generators in the home.
    # Print rows where 'own' is less than 0
    if df.loc[df["own"] < 0].shape[0] > 0:
        LOGGER.warning("Negative 'own' values found:")
        # Log the rows with negative 'own' values
        chunked_logger.log_df(df.loc[df["own"] < 0], floatfmt=".3f", level=logging.WARNING)
    # Set 'own' values less than 0 to 0
    df.loc[df["own"] < 0, "own"] = 0
    # the 'own' energy avoids the need to import energy from the grid
    # so the money avoided by 'own' is saved.
    df["saved_own"] = df["own"] * df["price"]
    # the 'exp'orted energy is the energy that is not used by the home but sold to the grid.
    # 2025: for now we assume selling at the hourly price.
    df["saved_exp"] = df["exp"] * df["price"]
    #
    # PV data for plotting
    #
    pv_balance = df[["gep", "solar", "gen"]].copy()
    pv_balance["solar"][df["gep"] < df["solar"]] = df["solar"] - df["gep"]
    pv_balance["solar"] *= -1
    pv_balance.rename(columns={"gep": "leveren", "solar": "opslag", "gen": "laden"}, inplace=True)
    # LOGGER.debug("\n\n ** PV data for plotting  **")
    # LOGGER.debug(pv_balance.to_markdown(floatfmt=".3f"))
    #
    # MAINS data for plotting
    #
    p1_balance = df[["exp", "own", "imp"]].copy()
    p1_balance.rename(
        columns={"exp": "verkopen", "own": "zelf gebruiken", "imp": "inkopen"}, inplace=True
    )
    #
    # EV data for plotting
    #
    ev_balance = df[["evn", "evp"]].copy()
    ev_balance.rename(columns={"evn": "laden", "evp": "leveren"}, inplace=True)
    # solar used for EV
    # df["EVsol"] = np.minimum(df["EVtotal"], solbalance)
    # imported and used for EV
    # df["EVnet"] = df["EVtotal"] - df["EVsol"]
    # compensate for import diverted to EV ...
    # df["import"] = df["imp"] - df["EVnet"]
    # ... and/or import
    # compensate for solar diverted to EV ...
    # df["EB"] = df["gep"] + df["export"] - df["EVsol"]
    # df["EB"] = df["PVtotal"] - df["EVsol"] + df["exp"]
    # ... and/or export ('export' is negative!)
    # df["EB"][df["EB"] < 0] = 0
    # LOGGER.debug("o  database charger processed data")
    # chunked_logger.log_df(df, floatfmt=".3f", level=logging.DEBUG)

    # df.drop(
    #     ["h1b", "h1d", "gen", "imp", "exp", "gep", "EVtotal", "SOLtotal", "P1total"],
    #     axis=1,
    #     inplace=True,
    #     errors="ignore",
    # )

    # put columns in the right order for plotting
    # categories = ["export", "import", "EB", "EVsol", "EVnet"]
    # df.columns = pd.CategoricalIndex(df.columns.values, ordered=True, categories=categories)
    df = df.sort_index(axis=1)
    LOGGER.debug("\n\n ** ALL data  **")
    chunked_logger.log_df(df, floatfmt=".3f", level=logging.DEBUG)

    df_euro = df[["saved_exp", "saved_own", "price"]].copy()
    df_euro["saved_own"] = df_euro["saved_own"].abs()
    df_euro["saved_exp"] = df_euro["saved_exp"].abs()
    df_euro["price"] = df_euro["price"] * df["gen"]
    df_euro.rename(
        columns={"saved_exp": "verkopen", "saved_own": "zelf gebruiken", "price": "dyn.inkopen"},
        inplace=True,
    )

    data_dict = {"PV": pv_balance, "HOME": p1_balance, "EV": ev_balance, "EURO": df_euro}
    _own = df_euro["zelf gebruiken"].sum()
    _exp = df_euro["verkopen"].sum()
    _ink = df_euro["dyn.inkopen"].sum()
    LOGGER.info(f"\nAvoided costs    : {_own:+.5f} euro")
    LOGGER.info(f"Exported earnings: {_exp:+.5f} euro")
    LOGGER.info(f"Buy unbalance    : {_ink:+.5f} euro")
    LOGGER.info(f"Total            : {_own + _exp + _ink:+.5f} euro")

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
    chunked_logger = ChunkedLogger(LOGGER)

    if locatorformat is None:
        locatorformat = ["hour", "%d-%m %Hh"]
    LOGGER.debug("\n\n*** PLOTTING ***")
    for parameter in data_dict:
        data_frame = data_dict[parameter]  # type: pd.DataFrame
        LOGGER.debug(parameter)
        chunked_logger.log_df(data_frame, floatfmt=".3f", level=logging.DEBUG)
        mjr_ticks = int(len(data_frame.index) / 40)
        if mjr_ticks <= 0:
            mjr_ticks = 1
        ticklabels = [""] * len(data_frame.index)
        ticklabels[::mjr_ticks] = [
            item.strftime(locatorformat[1]) for item in data_frame.index[::mjr_ticks]
        ]
        LOGGER.debug(ticklabels)
        if len(data_frame.index) == 0:
            LOGGER.debug("No data.")
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
                color=["blue", "seagreen", "red", "lightgreen", "salmon"],
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
            LOGGER.debug(f" --> {output_file}_{parameter}.png\n")


def main(opt) -> None:
    """
    This is the main loop
    """
    if opt.hours:
        plot_graph(
            cs.TREND["hour_graph"],
            fetch_data(hours_to_fetch=opt.hours, aggregation="H"),
            plot_title=f" trend afgelopen uren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            show_data=False,
            locatorformat=["hour", "%d-%m %Hh"],
        )
    if opt.days:
        plot_graph(
            cs.TREND["day_graph"],
            fetch_data(hours_to_fetch=opt.days * 24, aggregation="D"),
            plot_title=f" trend afgelopen dagen ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            show_data=False,
            locatorformat=["day", "%Y-%m-%d"],
        )
    if opt.months:
        plot_graph(
            cs.TREND["month_graph"],
            fetch_data(hours_to_fetch=opt.months * 31 * 24, aggregation="ME"),
            plot_title=f" trend afgelopen maanden ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            show_data=True,
            locatorformat=["month", "%Y-%m"],
        )
    if opt.years:
        plot_graph(
            cs.TREND["year_graph"],
            fetch_data(hours_to_fetch=opt.years * 366 * 24, aggregation="A"),
            plot_title=f" trend afgelopen jaren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            show_data=True,
            locatorformat=["year", "%Y"],
        )


if __name__ == "__main__":
    print(f"Trending (me) with Python {sys.version}")
    if OPTION.hours == 0:
        OPTION.hours = 80
    if OPTION.days == 0:
        OPTION.days = 10  # 80
    if OPTION.months == 0:
        OPTION.months = 2  # 6 * 12 + dt.now().month
    if OPTION.years == 0:
        OPTION.years = 1  # 10
    if OPTION.edate:
        print("NOT NOW")
        EDATETIME = f"'{OPTION.edate}'"

    if OPTION.debug:
        print(OPTION)
        if len(LOGGER.handlers) == 0:
            LOGGER.addHandler(logging.StreamHandler(sys.stdout))
        LOGGER.setLevel(logging.DEBUG)
        DEBUG = True
        print("DEBUG-mode started")
    main(OPTION)
