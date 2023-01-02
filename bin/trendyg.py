#!/usr/bin/env python3

"""Create multi-year graphs"""

import argparse
import time
from datetime import datetime as dt

import matplotlib.pyplot as plt
import numpy as np

import constants

# noinspection PyUnresolvedReferences
import libkamstrup as kl

DATABASE = constants.TREND["database"]
TABLE_MAINS = constants.KAMSTRUP["sql_table"]
TABLE_PRDCT = constants.SOLAREDGE["sql_table"]
TABLE_CHRGR = constants.ZAPPI["sql_table"]
OPTION = ""
DEBUG = False


def fetch_last_months(months_to_fetch):
    """..."""
    global DATABASE
    config = kl.add_time_line(
        {
            "grouping": "%Y-%m",
            "period": months_to_fetch,
            "timeframe": "month",
            "database": DATABASE,
            "table": TABLE_PRDCT,
        }
    )
    opwekking, prod_lbls = kl.get_historic_data(
        config, telwerk="energy", from_start_of_year=True
    )
    config["table"] = TABLE_MAINS
    import_lo, data_lbls = kl.get_historic_data(
        config, telwerk="T1in", from_start_of_year=True
    )
    import_hi, data_lbls = kl.get_historic_data(
        config, telwerk="T2in", from_start_of_year=True
    )
    export_lo, data_lbls = kl.get_historic_data(
        config, telwerk="T1out", from_start_of_year=True
    )
    export_hi, data_lbls = kl.get_historic_data(
        config, telwerk="T2out", from_start_of_year=True
    )
    # production data may not yet have caught up to the current hour
    if not (prod_lbls[-1] == data_lbls[-1]):
        opwekking = opwekking[:-1]
        np.append(opwekking, 0.0)
    return data_lbls, import_lo, import_hi, opwekking, export_lo, export_hi


def fetch_last_year(year_to_fetch):
    """..."""
    global DATABASE
    config = kl.add_time_line(
        {
            "grouping": "%Y-%m",
            "period": 12,
            "timeframe": "month",
            "database": DATABASE,
            "table": TABLE_PRDCT,
            "year": year_to_fetch,
        }
    )
    opwekking, prod_lbls = kl.get_historic_data(
        config, telwerk="energy", from_start_of_year=True
    )
    config["table"] = TABLE_MAINS
    import_lo, data_lbls = kl.get_historic_data(
        config, telwerk="T1in", from_start_of_year=True
    )
    import_hi, data_lbls = kl.get_historic_data(
        config, telwerk="T2in", from_start_of_year=True
    )
    export_lo, data_lbls = kl.get_historic_data(
        config, telwerk="T1out", from_start_of_year=True
    )
    export_hi, data_lbls = kl.get_historic_data(
        config, telwerk="T2out", from_start_of_year=True
    )
    # production data may not yet have caught up to the current hour
    if not (prod_lbls[-1] == data_lbls[-1]):
        opwekking = opwekking[:-1]
        np.append(opwekking, 0.0)
    return data_lbls, import_lo, import_hi, opwekking, export_lo, export_hi


def plot_graph(output_file, data_tuple, plot_title, gauge=False):
    """
    Create the graph
    """
    global OPTION
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
    grph_lbls, total_use, total_out = kl.build_arrays44(data_lbls, usage, exprt)
    if OPTION.print:
        np.set_printoptions(precision=3)
        print("data_lbls: ", np.shape(data_lbls), data_lbls[-12:])
        print(" ")
        print("opwekking: ", np.shape(opwekking), opwekking[-12:])
        print(" ")
        print("export_hi: ", np.shape(export_hi), export_hi[-12:])
        print("export_lo: ", np.shape(export_lo), export_lo[-12:])
        print("exprt    : ", np.shape(exprt), exprt[-12:])
        print(" ")
        print("import_hi: ", np.shape(import_hi), import_hi[-12:])
        print("import_lo: ", np.shape(import_lo), import_lo[-12:])
        print("imprt    : ", np.shape(imprt), imprt[-12:])
        print(" ")
        print("own_usage: ", np.shape(own_usage), own_usage[-12:])
        print("usage    : ", np.shape(usage), usage[-12:])
        print(" ")
        print(" ")
        # print("grph_lbls: ", np.shape(grph_lbls), grph_lbls)
        print("grph_lbls: ", grph_lbls)
        print(" ")
        # print("total_use: ", np.shape(total_use), total_use[yr])
        print("total_use: ", total_use)
        print(" ")
        # print("total_out: ", np.shape(total_out), total_out[yr])
        print("total_out: ", total_out)

    col_import = "red"
    col_export = "blue"
    col_iodif = "cyan"

    if not gauge:
        # Set the bar width
        bars_width = 0.9
        bar_width = bars_width / len(grph_lbls[0])
        # Set the color alpha
        ahpla = 1 - (1 / (len(grph_lbls[0]) + 1) * len(grph_lbls[0]))
        # positions of the left bar-boundaries
        tick_pos = np.arange(1, len(grph_lbls[1]) + 1) - (bars_width / 2)

        # Create the general plot and the bar
        plt.rc("font", size=6.5)
        dummy, ax1 = plt.subplots(1, figsize=(10, 3.5))

        # Create a bar plot usage
        for idx in range(0, len(grph_lbls[0])):
            ax1.bar(
                tick_pos + (idx * bar_width),
                total_use[idx],
                width=bar_width,
                label=grph_lbls[0][idx],
                alpha=ahpla + (idx * ahpla),
                color=col_import,
                align="edge",
            )
            # Create a bar plot of production
            ax1.bar(
                tick_pos + (idx * bar_width),
                [-1 * i for i in total_out[idx]],
                width=bar_width,
                alpha=ahpla + (idx * ahpla),
                color=col_export,
                align="edge",
            )

        # Set Axes stuff
        ax1.set_ylabel("[kWh]")
        ax1.set_xlabel("Datetime")
        ax1.set_xlim(
            [
                min(tick_pos) - (bars_width / 2),
                max(tick_pos) + (bars_width / 2 * 3),
            ]
        )
        ax1.grid(which="major", axis="y", color="k", linestyle="--", linewidth=0.5)
        ax1.axhline(y=0, color="k")
        ax1.axvline(x=0, color="k")
        plt.xticks(tick_pos + (bars_width / 2), grph_lbls[1])
    else:
        power_in = np.sum(imprt)
        power_out = np.sum(exprt)
        power_dif = power_out - power_in
        if power_in > power_out:
            col_iodif = "orange"
        power_rng = 2 * max(power_in, power_out)
        if OPTION.print:
            print(f"IN  {power_in:.0f}")
            print(f"OUT {power_out:.0f}")
            print(f"DIF {power_dif:.0f}")
            print(f"RNG {power_rng:.0f}")

        # Set the bar width
        bars_width = 1.0
        # bar_width = bars_width / len(grph_lbls[0])
        # Set the color alpha
        ahpla = 0.7
        # 1 - (1 / (len(grph_lbls[0]) + 1) * len(grph_lbls[0]))
        # positions of the left bar-boundaries
        tick_pos = 0

        # Create the general plot and the bar
        plt.rc("font", size=6.5)
        dummy, ax1 = plt.subplots(1, figsize=(10, 1.5))

        ax1.barh(
            tick_pos,
            power_out,
            height=bars_width,
            alpha=ahpla,
            color=col_export,
            left=power_rng / -2,
            align="edge",
        )
        ax1.text(
            power_rng / -3,
            tick_pos + (bars_width / 2),
            "{:4.0f}".format(power_out),
            {"ha": "center", "va": "center"},
            fontsize=12,
        )
        ax1.barh(
            tick_pos,
            abs(power_dif),
            height=bars_width,
            alpha=ahpla * 0.5,
            color=col_iodif,
            left=(power_rng / -2) + power_out,
            align="edge",
        )
        ax1.text(
            (power_rng / -2) + power_out + abs(power_dif) / 2,
            tick_pos + (bars_width / 2),
            "{:4.0f}".format(power_dif),
            {"ha": "center", "va": "center"},
            fontsize=12,
        )
        ax1.barh(
            tick_pos,
            power_in,
            height=bars_width,
            alpha=ahpla,
            color=col_import,
            left=(power_rng / -2) + power_out + abs(power_dif),
            align="edge",
        )
        ax1.text(
            power_rng / 3,
            tick_pos + (bars_width / 2),
            "{:4.0f}".format(power_in),
            {"ha": "center", "va": "center"},
            fontsize=12,
        )

        # Set  Axes stuff
        ax1.set_xlabel("[kWh]")
        ax1.grid(which="major", axis="x", color="k", linestyle="--", linewidth=0.5)
        ax1.set_xlim([power_rng / -2, power_rng / 2])
        # ax1.axhline(y=0, color='k')
        ax1.axvline(x=0, color="k")
        ax1.set_yticks([1])

    # Set general plot stuff
    plt.title(f"{plot_title}")
    if not gauge:
        plt.legend(loc="upper left", ncol=6, framealpha=0.2)
    # Fit every nicely
    plt.tight_layout()
    plt.savefig(fname=f"{output_file}.png", format="png")


def main():
    """
    This is the main loop
    """
    global OPTION

    if OPTION.months:
        plot_graph(
            constants.TREND["yg_vs_month"],
            fetch_last_months(OPTION.months),
            f"Stroomverbruik/levering per maand afgelopen jaren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
        )
    if OPTION.gauge:
        plot_graph(
            constants.TREND["yg_gauge"],
            fetch_last_year(OPTION.gauge),
            f"Salderingsbalans over {OPTION.gauge} ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
            gauge=True,
        )


if __name__ == "__main__":
    year_to_graph = int(time.strftime("%Y", time.localtime()))
    parser = argparse.ArgumentParser(description="Create trendgraph or gauge")
    parser.add_argument(
        "-g",
        "--gauge",
        type=int,
        help="generate a gauge. Specify year to aggregate or 0 for current " "year.",
    )
    parser.add_argument(
        "-m",
        "--months",
        type=int,
        help="number of months of data to use for the graph or 0 for " "default.",
    )
    parser.add_argument(
        "-p", "--print", action="store_true", help="Output data to stdout."
    )
    OPTION = parser.parse_args()
    if OPTION.months == 0:
        OPTION.months = 61
    if (OPTION.gauge is not None) and (
        OPTION.gauge == 0 or OPTION.gauge > year_to_graph
    ):
        OPTION.gauge = year_to_graph
    main()
