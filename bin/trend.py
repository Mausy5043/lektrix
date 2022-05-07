#!/usr/bin/env python3

"""Create trendbargraphs of the data for various periods."""

import argparse
from datetime import datetime as dt
import sqlite3 as s3
import pandas as pd

import matplotlib.pyplot as plt
import numpy as np

import constants

DATABASE = constants.TREND['database']
TABLE_RHT = constants.TREND['sql_table_rht']
TABLE_AC = constants.TREND['sql_table_ac']
ROOMS = constants.ROOMS
DEVICE_LIST = constants.DEVICES
AIRCO_LIST = constants.AIRCO
OPTION = ""
DEBUG = False


def fetch_data(hours_to_fetch=48, aggregation=1):
    data_dict_rht = fetch_data_rht(hours_to_fetch=hours_to_fetch, aggregation=aggregation)
    data_dict_ac = fetch_data_ac(hours_to_fetch=hours_to_fetch, aggregation=aggregation)
    data_dict = dict()
    # move outside temperature from Daikin to the table with the other temperature sensors
    for d in data_dict_ac:
        if 'T(out)' in data_dict_ac[d]:
            data_dict_rht['temperature']['T(out)'] = data_dict_ac[d]['T(out)']
            data_dict_ac[d].drop(['T(out)'], axis=1, inplace=True, errors='ignore')
    for d in data_dict_rht:
        data_dict[d] = data_dict_rht[d]
    for d in data_dict_ac:
        data_dict[d] = data_dict_ac[d]
    return data_dict


def fetch_data_ac(hours_to_fetch=48, aggregation=1):
    """
    Query the database to fetch the requested data
    :param hours_to_fetch:      (int) number of hours of data to fetch
    :param aggregation:         (int) number of minutes to aggregate per datapoint
    :return:
    """
    df_cmp = None
    df_t = None
    if DEBUG:
        print("*** fetching AC ***")
    for airco in AIRCO_LIST:
        airco_id = airco['name']
        where_condition = f" (sample_time >= datetime(\'now\', \'-{hours_to_fetch + 1} hours\'))" \
                          f" AND (room_id LIKE \'{airco_id}\')"
        s3_query = f"SELECT * FROM {TABLE_AC} WHERE {where_condition}"
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
        df.index = pd.to_datetime(df.index, unit='s').tz_localize("UTC").tz_convert("Europe/Amsterdam")
        # resample to monotonic timeline
        df = df.resample(f'{aggregation}min').mean()
        df = df.interpolate(method='slinear')
        # remove temperature target values for samples when the AC is turned off.
        df.loc[df.ac_power == 0, 'temperature_target'] = np.nan
        # conserve memory; we dont need the these.
        df.drop(['ac_mode', 'ac_power', 'room_id'], axis=1, inplace=True, errors='ignore')
        df_cmp = collate(df_cmp, df,
                         columns_to_drop=['temperature_ac', 'temperature_target', 'temperature_outside'],
                         column_to_rename='cmp_freq',
                         new_name=airco_id
                         )
        if df_t is None:
            df = collate(None, df,
                         columns_to_drop=['cmp_freq'],
                         column_to_rename='temperature_ac',
                         new_name=airco_id
                         )
            df_t = collate(df_t, df,
                           columns_to_drop=[],
                           column_to_rename='temperature_target',
                           new_name=f'{airco_id}_tgt'
                           )
        else:
            df = collate(None, df,
                         columns_to_drop=['cmp_freq', 'temperature_outside'],
                         column_to_rename='temperature_ac',
                         new_name=airco_id
                         )
            df_t = collate(df_t, df,
                           columns_to_drop=[],
                           column_to_rename='temperature_target',
                           new_name=f'{airco_id}_tgt'
                           )

    # create a new column containing the max value of both aircos, then remove the airco_ columns
    df_cmp['cmp_freq'] = df_cmp[['airco0', 'airco1']].apply(np.max, axis=1)
    df_cmp.drop(['airco0', 'airco1'], axis=1, inplace=True, errors='ignore')
    if DEBUG:
        print(df_cmp)
    # rename the column to something shorter or drop it
    if OPTION.outside:
        df_t.rename(columns={'temperature_outside': 'T(out)'}, inplace=True)
    else:
        df_t.drop(['temperature_outside'], axis=1, inplace=True, errors='ignore')
    if DEBUG:
        print(df_t)

    ac_data_dict = {'temperature_ac': df_t, 'compressor': df_cmp}
    return ac_data_dict


def fetch_data_rht(hours_to_fetch=48, aggregation=1):
    """
    Query the database to fetch the requested data
    :param hours_to_fetch:      (int) number of hours of data to fetch
    :param aggregation:         (int) number of minutes to aggregate per datapoint
    :return:
    """
    if DEBUG:
        print("*** fetching RHT ***")
    df_t = df_h = df_v = None
    for device in DEVICE_LIST:
        room_id = device[1]
        where_condition = f" (sample_time >= datetime(\'now\', \'-{hours_to_fetch + 1} hours\'))" \
                          f" AND (room_id LIKE \'{room_id}\')"
        s3_query = f"SELECT * FROM {TABLE_RHT} WHERE {where_condition}"
        if DEBUG:
            print(s3_query)
        with s3.connect(DATABASE) as con:
            df = pd.read_sql_query(s3_query,
                                   con,
                                   parse_dates='sample_time',
                                   index_col='sample_epoch'
                                   )
        # conserve memory; we dont need the room_id repeated in every row.
        df.drop('room_id', axis=1, inplace=True, errors='ignore')
        for c in df.columns:
            if c not in ['sample_time']:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        df.index = pd.to_datetime(df.index, unit='s').tz_localize("UTC").tz_convert("Europe/Amsterdam")
        # resample to monotonic timeline
        df = df.resample(f'{aggregation}min').mean()
        df = df.interpolate(method='slinear')
        try:
            new_name = ROOMS[room_id]
        except KeyError:
            new_name = room_id
        df.drop('sample_time', axis=1, inplace=True, errors='ignore')
        df_t = collate(df_t, df,
                       columns_to_drop=['voltage', 'humidity'],
                       column_to_rename='temperature',
                       new_name=new_name
                       )

        df_h = collate(df_h, df,
                       columns_to_drop=['temperature', 'voltage'],
                       column_to_rename='humidity',
                       new_name=new_name
                       )

        df_v = collate(df_v, df,
                       columns_to_drop=['temperature', 'humidity'],
                       column_to_rename='voltage',
                       new_name=new_name
                       )

    if DEBUG:
        print(f"TEMPERATURE\n", df_t)
        print(f"HUMIDITY\n", df_h)
        print(f"VOLTAGE\n", df_v)
    rht_data_dict = {'temperature': df_t, 'humidity': df_h, 'voltage': df_v}
    return rht_data_dict


def collate(prev_df, data_frame, columns_to_drop=[], column_to_rename='', new_name='room_id'):
    # drop the 'columns_to_drop'
    for col in columns_to_drop:
        data_frame = data_frame.drop(col, axis=1, errors='ignore')
    # rename the 'column_to_rename'
    data_frame.rename(columns={f'{column_to_rename}': new_name}, inplace=True)
    # collate both dataframes
    if prev_df is not None:
        data_frame = pd.merge(prev_df, data_frame, left_index=True, right_index=True, how='left')
    return data_frame


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
        print("*** plotting ***")
    for parameter in data_dict:
        if DEBUG:
            print(parameter)
        data_frame = data_dict[parameter]
        fig_x = 20
        fig_y = 7.5
        fig_fontsize = 13
        ahpla = 0.7
        """
        # ###############################
        # Create a line plot of temperatures
        # ###############################
        """
        plt.rc('font', size=fig_fontsize)
        ax1 = data_frame.plot(kind='line',
                              marker='.',
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
                    format='png',
                    # bbox_inches='tight'
                    )


def main():
    """
    This is the main loop
    """
    if OPTION.hours:
        aggr = int(float(OPTION.hours) * 60. / 480.)
        if aggr < 1:
            aggr = 1
        plot_graph(constants.TREND['day_graph'],
                   fetch_data(hours_to_fetch=OPTION.hours, aggregation=aggr),
                   f" trend afgelopen dagen ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
                   )
    if OPTION.days:
        aggr = int(float(OPTION.days) * 24. * 60. / 5760.)
        if aggr < 1:
            aggr = 1
        plot_graph(constants.TREND['month_graph'],
                   fetch_data(hours_to_fetch=OPTION.days * 24, aggregation=aggr),
                   f" trend per uur afgelopen maand ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
                   )
    if OPTION.months:
        aggr = int(float(OPTION.months) * 30.5 * 24. * 60. / 9900.)
        if aggr < 1:
            aggr = 1
        plot_graph(constants.TREND['year_graph'],
                   fetch_data(hours_to_fetch=OPTION.months * 31 * 24, aggregation=aggr),
                   f" trend per dag afgelopen maanden ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
                   )
    if OPTION.years:
        aggr = int(float(OPTION.years) * 30.5 * 24. * 60. / 9900.)
        if aggr < 1:
            aggr = 1
        plot_graph(constants.TREND['year_graph'],
                   fetch_data(hours_to_fetch=OPTION.months * 31 * 24, aggregation=aggr),
                   f" trend per dag afgelopen maanden ({dt.now().strftime('%d-%m-%Y %H:%M:%S')})",
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
