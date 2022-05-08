#!/usr/bin/env python3

"""Create trendbargraphs of the data for various periods."""

import argparse
import sqlite3 as s3
from datetime import datetime as dt

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import constants

DATABASE = constants.TREND['database']
TABLE_MAINS = constants.KAMSTRUP['sql_table']
TABLE_PRDCT = constants.SOLAREDGE['sql_table']
TABLE_CHRGR = constants.ZAPPI['sql_table']
OPTION = ""
DEBUG = False


def fetch_data(hours_to_fetch=48, aggregation=1):
    data_dict_mains = fetch_data_mains(hours_to_fetch=hours_to_fetch, aggregation=aggregation)
    data_dict_prod = fetch_data_production(hours_to_fetch=hours_to_fetch, aggregation=aggregation)
    data_dict_chrg = fetch_data_charger(hours_to_fetch=hours_to_fetch, aggregation=aggregation)
    data_dict = dict()

    for d in data_dict_mains:
        data_dict[d] = data_dict_mains[d]
    for d in data_dict_prod:
        data_dict[d] = data_dict_prod[d]
    for d in data_dict_chrg:
        data_dict[d] = data_dict_chrg[d]
    if DEBUG:
        print(f"\n\n")
        print(data_dict)
    return data_dict


def fetch_data_mains(hours_to_fetch=48, aggregation=1):
    """
    Query the database to fetch the requested data

    Args:
        hours_to_fetch (int):      number of hours of data to fetch
        aggregation (int):         number of minutes to aggregate per datapoint

    Returns:
        dict with data
    """
    df_cmp = None
    df_t = None
    if DEBUG:
        print("\n*** fetching MAINS data ***")
    where_condition = f" (sample_time >= datetime(\'now\', \'-{hours_to_fetch + 1} hours\'))"
    s3_query = f"SELECT * FROM {TABLE_MAINS} WHERE {where_condition}"
    if DEBUG:
        print(s3_query)
    with s3.connect(DATABASE) as con:
        df = pd.read_sql_query(s3_query,
                               con,
                               parse_dates='sample_time',
                               index_col='sample_epoch'
                               )
    for c in df.columns:
        if c not in ['sample_time']:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    df.index = pd.to_datetime(df.index, unit='s')
    # resample to monotonic timeline
    df = df.resample(f'{aggregation}min', label='right').max()
    # df = df.interpolate(method='bfill')

    df.drop('sample_time', axis=1, inplace=True, errors='ignore')
    df.drop(['powerin', 'powerout', 'tarif', 'swits'], axis=1, inplace=True, errors='ignore')
    df = df.diff()  # KAMSTRUP data contains totalisers, we need the differential per timeframe
    df['T1in'] *= 0.001     # -> kWh
    df['T2in'] *= 0.001     # -> kWh
    df['T1out'] *= -0.001   # -> kWh export
    df['T2out'] *= -0.001   # -> kWh export
    if DEBUG:
        print(df)
    mains_data_dict = {'mains': df}
    return mains_data_dict


def fetch_data_production(hours_to_fetch=48, aggregation=1):
    """
    Query the database to fetch the requested data

    Args:
        hours_to_fetch (int):      number of hours of data to fetch
        aggregation (int):         number of minutes to aggregate per datapoint

    Returns:
        dict with data
    """
    if DEBUG:
        print("\n*** fetching PRODUCTION data ***")
    where_condition = f" (sample_time >= datetime(\'now\', \'-{hours_to_fetch + 1} hours\'))"
    s3_query = f"SELECT * FROM {TABLE_PRDCT} WHERE {where_condition}"
    if DEBUG:
        print(s3_query)
    with s3.connect(DATABASE) as con:
        df = pd.read_sql_query(s3_query,
                               con,
                               parse_dates='sample_time',
                               index_col='sample_epoch'
                               )
    for c in df.columns:
        if c not in ['sample_time']:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    # df.index = pd.to_datetime(df.index, unit='s').tz_localize("UTC").tz_convert("Europe/Amsterdam")
    df.index = pd.to_datetime(df.index, unit='s')

    # resample to monotonic timeline
    df = df.resample(f'{aggregation}min', label='right').mean()
    # df = df.interpolate(method='bfill')

    df.drop('sample_time', axis=1, inplace=True, errors='ignore')
    if DEBUG:
        print(df)
    prod_data_dict = {'production': df}
    return prod_data_dict


def fetch_data_charger(hours_to_fetch=48, aggregation=1):
    """
    Query the database to fetch the requested data

    Args:
        hours_to_fetch (int):      number of hours of data to fetch
        aggregation (int):         number of minutes to aggregate per datapoint

    Returns:
        dict with data
    """
    if DEBUG:
        print("\n*** fetching CHARGER data ***")
    where_condition = f" (sample_time >= datetime(\'now\', \'-{hours_to_fetch + 1} hours\'))"
    s3_query = f"SELECT * FROM {TABLE_CHRGR} WHERE {where_condition}"
    if DEBUG:
        print(s3_query)
    with s3.connect(DATABASE) as con:
        df = pd.read_sql_query(s3_query,
                               con,
                               parse_dates='sample_time',
                               index_col='sample_epoch'
                               )
    for c in df.columns:
        if c not in ['sample_time']:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    # df.index = pd.to_datetime(df.index, unit='s').tz_localize("UTC").tz_convert("Europe/Amsterdam")
    df.index = pd.to_datetime(df.index, unit='s')
    # resample to monotonic timeline
    df = df.resample(f'{aggregation}min', label='right').mean()
    # df = df.interpolate(method='bfill')

    df.drop('sample_time', axis=1, inplace=True, errors='ignore')
    if DEBUG:
        print(df)
    prod_data_dict = {'charger': df}
    return prod_data_dict


def remove_nans(frame, col_name, default):
    """remove NANs from a series"""
    for idx, tmpr in enumerate(frame[col_name]):
        if np.isnan(tmpr):
            if idx == 0:
                frame.at[idx, col_name] = default
            else:
                frame.at[idx, col_name] = frame.at[idx - 1, col_name]
    return frame


def plot_graph(output_file, data_dict, plot_title):
    """
    Plot the data into a graph

    :param output_file: (str) name of the trendgraph file
    :param data_dict: (dict) contains the data for the lines. Each paramter is a separate pandas Dataframe
                      {'df': Dataframe}
    :param plot_title: (str) title to be displayed above the plot
    :return: None
    """
    if DEBUG:
        print("\n\n*** PLOTTING ***")
    for parameter in data_dict:
        if DEBUG:
            print(parameter)
        data_frame = data_dict[parameter]  # type: pd.DataFrame
        if len(data_frame.index) == 0:
            if DEBUG:
                print("No data.")
        else:
            fig_x = 20
            fig_y = 7.5
            fig_fontsize = 13
            ahpla = 0.7

            # create a line plot
            plt.rc('font', size=fig_fontsize)
            ax1 = data_frame.plot.bar(stacked=True,
                                      figsize=(fig_x, fig_y)
                                      )
            # linewidth and alpha need to be set separately
            for i, l in enumerate(ax1.lines):
                plt.setp(l, alpha=ahpla, linewidth=1, linestyle=' ')
            ax1.set_ylabel(parameter)
            ax1.legend(loc='lower left',
                       ncol=8,
                       framealpha=0.2
                       )
            ax1.set_xlabel("Datetime")
            ax1.grid(which='major',
                     axis='y',
                     color='k',
                     linestyle='--',
                     linewidth=0.5
                     )
            plt.title(f'{parameter} {plot_title}')
            plt.tight_layout()
            plt.savefig(fname=f'{output_file}_{parameter}.png',
                        format='png'
                        )
            if DEBUG:
                print(f" --> {output_file}_{parameter}.png\n")


def main():
    """
    This is the main loop
    """
    if OPTION.hours:
        aggr = 60  # int(float(OPTION.hours) * 60. / 480)
        if aggr < 1:
            aggr = 1
        plot_graph(constants.TREND['hour_graph'],
                   fetch_data(hours_to_fetch=OPTION.hours, aggregation=aggr),
                   f" trend afgelopen uren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
                   )
    if OPTION.days:
        aggr = 60 * 24  # int(float(OPTION.days) * 24. * 60. / 5760.)
        if aggr < 1:
            aggr = 1
        plot_graph(constants.TREND['day_graph'],
                   fetch_data(hours_to_fetch=OPTION.days * 24, aggregation=aggr),
                   f" trend afgelopen dagen ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
                   )
    if OPTION.months:
        aggr = 60 * 24 * 31  # int(float(OPTION.months) * 30.5 * 24. * 60.  / 9900.)
        if aggr < 1:
            aggr = 1
        plot_graph(constants.TREND['month_graph'],
                   fetch_data(hours_to_fetch=OPTION.months * 31 * 24, aggregation=aggr),
                   f" trend afgelopen maanden ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
                   )
    if OPTION.years:
        aggr = 24 * 60 * 366  # int(float(OPTION.years) * 366 * 24. * 60.)
        if aggr < 1:
            aggr = 1
        plot_graph(constants.TREND['year_graph'],
                   fetch_data(hours_to_fetch=OPTION.years * 366 * 24, aggregation=aggr),
                   f" trend afgelopen jaren ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
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
        OPTION.hours = 80
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
