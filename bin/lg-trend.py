#!/usr/bin/env python3

"""Create trendbargraphs for various periods of electricity use and production."""

# NOTE: Due to ms-trend.py not working properly, the legacy trend.py is provided to do the trending.

import argparse
from datetime import datetime as dt

import matplotlib.pyplot as plt
import numpy as np

import constants
# noinspection PyUnresolvedReferences
import libkamstrup as kl

DATABASE = constants.TREND['database']
TABLE_MAINS = constants.KAMSTRUP['sql_table']
TABLE_PRDCT = constants.SOLAREDGE['sql_table']
TABLE_CHRGR = constants.ZAPPI['sql_table']
OPTION = ""
DEBUG = False


def fetch_last_day(hours_to_fetch):
    """Retrieve data with hour grouping. Ideally suited for a limited number of days.

    Args:
        hours_to_fetch (int): Number of hours to retrieve.

    Returns:
        arrays containing label texts and data
    """
    config = kl.add_time_line({"grouping": "%m-%d %Hh",
                               "period": hours_to_fetch,
                               "timeframe": "hour",
                               "database": DATABASE,
                               "table": TABLE_MAINS,
                               }
                              )

    import_lo, data_lbls = kl.get_historic_data(config, telwerk="T1in")
    if DEBUG:
        print(data_lbls)
        print(import_lo)
    import_hi, data_lbls = kl.get_historic_data(config, telwerk="T2in")
    if DEBUG:
        print(import_hi)
    export_lo, data_lbls = kl.get_historic_data(config, telwerk="T1out")
    if DEBUG:
        print(export_lo)
    export_hi, data_lbls = kl.get_historic_data(config, telwerk="T2out")
    if DEBUG:
        print(export_hi)

    config["table"] = TABLE_PRDCT
    opwekking, prod_lbls = kl.get_historic_data(config, telwerk="energy", dif=False)
    if DEBUG:
        print(prod_lbls)
        print(opwekking)
    # production data may not yet have caught up to the current hour
    if not (prod_lbls[-1] == data_lbls[-1]):
        opwekking = opwekking[:-1]
        np.append(opwekking, 0.0)
    if DEBUG:
        print(prod_lbls)
        print(opwekking)
    return data_lbls, import_lo, import_hi, opwekking, export_lo, export_hi


def fetch_last_month(days_to_fetch):
    """...
    """
    global DATABASE
    config = kl.add_time_line({"grouping": "%m-%d",
                               "period": days_to_fetch,
                               "timeframe": "day",
                               "database": DATABASE,
                               "table": TABLE_MAINS,
                               }
                              )
    import_lo, data_lbls = kl.get_historic_data(config, telwerk="T1in")
    import_hi, data_lbls = kl.get_historic_data(config, telwerk="T2in")
    export_lo, data_lbls = kl.get_historic_data(config, telwerk="T1out")
    export_hi, data_lbls = kl.get_historic_data(config, telwerk="T2out")

    config["table"] = TABLE_PRDCT
    opwekking, prod_lbls = kl.get_historic_data(config, telwerk="energy", dif=False)
    # production data may not yet have caught up to the current hour
    if not (prod_lbls[-1] == data_lbls[-1]):
        opwekking = opwekking[:-1]
        np.append(opwekking, 0.0)
    return data_lbls, import_lo, import_hi, opwekking, export_lo, export_hi


def fetch_last_year(months_to_fetch):
    """...
    """
    global DATABASE
    config = kl.add_time_line({"grouping": "%Y-%m",
                               "period": months_to_fetch,
                               "timeframe": "month",
                               "database": DATABASE,
                               "table": TABLE_MAINS,
                               }
                              )
    import_lo, data_lbls = kl.get_historic_data(config,
                                                telwerk="T1in",
                                                from_start_of_year=True
                                                )
    import_hi, data_lbls = kl.get_historic_data(config,
                                                telwerk="T2in",
                                                from_start_of_year=True
                                                )
    export_lo, data_lbls = kl.get_historic_data(config,
                                                telwerk="T1out",
                                                from_start_of_year=True
                                                )
    export_hi, data_lbls = kl.get_historic_data(config,
                                                telwerk="T2out",
                                                from_start_of_year=True
                                                )

    config["table"] = TABLE_PRDCT
    opwekking, prod_lbls = kl.get_historic_data(config,
                                                telwerk="energy",
                                                from_start_of_year=True,
                                                dif=False
                                                )
    # production data may not yet have caught up to the current hour
    if not (prod_lbls[-1] == data_lbls[-1]):
        opwekking = opwekking[:-1]
        np.append(opwekking, 0.0)
    return data_lbls, import_lo, import_hi, opwekking, export_lo, export_hi


def fetch_last_years(years_to_fetch):
    """...
    """
    global DATABASE
    config = kl.add_time_line({"grouping": "%Y",
                               "period": years_to_fetch,
                               "timeframe": "year",
                               "database": DATABASE,
                               "table": TABLE_MAINS,
                               }
                              )
    import_lo, data_lbls = kl.get_historic_data(config,
                                                telwerk="T1in",
                                                from_start_of_year=True
                                                )
    import_hi, data_lbls = kl.get_historic_data(config,
                                                telwerk="T2in",
                                                from_start_of_year=True
                                                )
    export_lo, data_lbls = kl.get_historic_data(config,
                                                telwerk="T1out",
                                                from_start_of_year=True
                                                )
    export_hi, data_lbls = kl.get_historic_data(config,
                                                telwerk="T2out",
                                                from_start_of_year=True
                                                )

    config["table"] = TABLE_PRDCT
    opwekking, prod_lbls = kl.get_historic_data(config,
                                                telwerk="energy",
                                                from_start_of_year=True,
                                                dif=False
                                                )
    # production data may not yet have caught up to the current hour
    if not (prod_lbls[-1] == data_lbls[-1]):
        opwekking = opwekking[:-1]
        np.append(opwekking, 0.0)
    return data_lbls, import_lo, import_hi, opwekking, export_lo, export_hi


def plot_graph(output_file, data_tuple, plot_title, show_data=0):
    """...
    """
    data_lbls = data_tuple[0]
    import_lo = data_tuple[1]
    import_hi = data_tuple[2]
    opwekking = data_tuple[3]
    export_lo = data_tuple[4]
    export_hi = data_tuple[5]
    imprt = kl.contract(import_lo, import_hi)
    exprt = kl.contract(export_lo, export_hi)
    own_usage = kl.distract(opwekking, exprt)
    usage = kl.contract(own_usage, imprt)
    btm_hi = kl.contract(import_lo, own_usage)
    if DEBUG:
        plot_title = " ".join(["(DEBUG)", plot_title])
        np.set_printoptions(precision=3)
        print("data_lbls: ", np.size(data_lbls), data_lbls[-5:])
        print(" ")
        print("opwekking: ", np.size(opwekking), opwekking[-5:])
        print(" ")
        print("export_hi: ", np.size(export_hi), export_hi[-5:])
        print("export_lo: ", np.size(export_lo), export_lo[-5:])
        print("exprt    : ", np.size(exprt), exprt[-5:])
        print(" ")
        print("import_hi: ", np.size(import_hi), import_hi[-5:])
        print("import_lo: ", np.size(import_lo), import_lo[-5:])
        print("imprt    : ", np.size(imprt), imprt[-5:])
        print(" ")
        print("own_usage: ", np.size(own_usage), own_usage[-5:])
        print("usage    : ", np.size(usage), usage[-5:])
        print(" ")
        print("btm_hi   : ", np.size(btm_hi), btm_hi[-5:])

    # Set the bar width
    bar_width = 0.75
    # Set the color alpha
    ahpla = 0.7
    # positions of the left bar-boundaries
    tick_pos = list(range(1, len(data_lbls) + 1))

    # Create the general plot and the bar
    plt.rc("font", size=6.5)
    dummy, ax1 = plt.subplots(1, figsize=(10, 3.5))
    col_import = "red"
    col_export = "blue"
    col_usage = "green"

    # Create a bar plot of import_lo
    ax1.bar(tick_pos,
            import_hi,
            width=bar_width,
            label="Inkoop (normaal)",
            alpha=ahpla,
            color=col_import,
            align="center",
            bottom=btm_hi,  # [sum(i) for i in zip(import_lo, own_usage)]
            )
    # Create a bar plot of import_hi
    ax1.bar(tick_pos,
            import_lo,
            width=bar_width,
            label="Inkoop (dal)",
            alpha=ahpla * 0.5,
            color=col_import,
            align="center",
            bottom=own_usage,
            )
    # Create a bar plot of own_usage
    ax1.bar(tick_pos,
            own_usage,
            width=bar_width,
            label="Eigen gebruik",
            alpha=ahpla,
            color=col_usage,
            align="center",
            )
    if show_data == 1:
        for i, v in enumerate(own_usage):
            ax1.text(tick_pos[i],
                     10,
                     "{:7.3f}".format(v),
                     {"ha": "center", "va": "bottom"},
                     rotation=-90,
                     )
    if show_data == 2:
        for i, v in enumerate(usage):
            ax1.text(tick_pos[i],
                     500,
                     "{:4.0f}".format(v),
                     {"ha": "center", "va": "bottom"},
                     fontsize=12,
                     )
    # Exports hang below the y-axis
    # Create a bar plot of export_lo
    ax1.bar(tick_pos,
            [-1 * i for i in export_lo],
            width=bar_width,
            label="Verkoop (dal)",
            alpha=ahpla * 0.5,
            color=col_export,
            align="center",
            )
    # Create a bar plot of export_hi
    ax1.bar(tick_pos,
            [-1 * i for i in export_hi],
            width=bar_width,
            label="Verkoop (normaal)",
            alpha=ahpla,
            color=col_export,
            align="center",
            bottom=[-1 * i for i in export_lo],
            )
    if show_data == 1:
        for i, v in enumerate(exprt):
            ax1.text(tick_pos[i],
                     -10,
                     "{:7.3f}".format(v),
                     {"ha": "center", "va": "top"},
                     rotation=-90,
                     )
    if show_data == 2:
        for i, v in enumerate(exprt):
            ax1.text(tick_pos[i],
                     -500,
                     "{:4.0f}".format(v),
                     {"ha": "center", "va": "top"},
                     fontsize=12,
                     )

    # Set Axes stuff
    ax1.set_ylabel("[kWh]")
    if show_data == 0:
        y_lo = -1 * (max(exprt) + 1)
        y_hi = max(usage) + 1
        if y_lo > -1.5:
            y_lo = -1.5
        if y_hi < 1.5:
            y_hi = 1.5
        ax1.set_ylim([y_lo, y_hi])

    ax1.set_xlabel("Datetime")
    ax1.grid(which="major",
             axis="y",
             color="k",
             linestyle="--",
             linewidth=0.5
             )
    ax1.axhline(y=0, color="k")
    ax1.axvline(x=0, color="k")
    # Set plot stuff
    plt.xticks(tick_pos, data_lbls, rotation=-60)
    plt.title(f"{plot_title}")
    plt.legend(loc="upper left", ncol=5, framealpha=0.2)
    # Fit every nicely
    plt.xlim([min(tick_pos) - bar_width, max(tick_pos) + bar_width])
    plt.tight_layout()
    plt.savefig(fname=f"{output_file}_mains.png", format="png")


def main():
    """
    This is the main loop
    """
    if OPTION.hours:
        plot_graph(constants.TREND['hour_graph'],
                   fetch_last_day(OPTION.hours),
                   f" trend afgelopen uren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
                   )
    if OPTION.days:
        plot_graph(constants.TREND['day_graph'],
                   fetch_last_month(OPTION.days),
                   f"trend afgelopen dagen ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
                   )
    if OPTION.months:
        plot_graph(constants.TREND['month_graph'],
                   fetch_last_year(OPTION.months),
                   f"trend afgelopen maanden ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
                   show_data=1,
                   )
    if OPTION.years:
        plot_graph(constants.TREND['year_graph'],
                   fetch_last_years(OPTION.years),
                   f"Energietrend per jaar afgelopen jaren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
                   show_data=2,
                   )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a trendgraph")
    parser.add_argument("-hr",
                        "--hours",
                        type=int,
                        help="create hour-trend for last <HOURS> hours",
                        )
    parser.add_argument("-d",
                        "--days",
                        type=int,
                        help="create day-trend for last <DAYS> days"
                        )
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
    OPTION = parser.parse_args()
    if OPTION.hours == 0:
        OPTION.hours = 6 * 12
    if OPTION.days == 0:
        OPTION.days = 80
    if OPTION.months == 0:
        OPTION.months = 38
    if OPTION.years == 0:
        OPTION.years = 6

    if OPTION.debug:
        print(OPTION)
        DEBUG = True
        print("DEBUG-mode started")
    main()
