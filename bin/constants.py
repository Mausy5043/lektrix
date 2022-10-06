#!/usr/bin/env python3

import os
import sys

import pytz

_MYHOME = os.environ["HOME"]
_DATABASE = '/srv/databases/lektrix.sqlite3'
_WEBSITE = '/tmp/lektrix/site'

if not os.path.isfile(_DATABASE):
    _DATABASE = '/srv/data/lektrix.sqlite3'
if not os.path.isfile(_DATABASE):
    _DATABASE = '/mnt/data/lektrix.sqlite3'
if not os.path.isfile(_DATABASE):
    _DATABASE = f'.local/lektrix.sqlite3'
if not os.path.isfile(_DATABASE):
    _DATABASE = f'{_MYHOME}/.sqlite3/lektrix.sqlite3'
if not os.path.isfile(_DATABASE):
    print("Database is missing.")
    sys.exit(1)

DT_FORMAT = "%Y-%m-%d %H:%M:%S"
TIMEZONE = pytz.timezone("Europe/Amsterdam")

BATTERY = {'database': _DATABASE,
           'sql_table': "storage",

           'graph_file': ".local/graph.png",

           'sql_command': "INSERT INTO storage ("
                          "sample_time, sample_epoch, battery_id, soc"
                          ") "
                          "VALUES (?, ?, ?, ?)",
           'report_time': 299,
           'samplespercycle': 1,
           'template': {'sample_time': "dd-mmm-yyyy hh:mm:ss",
                        'sample_epoch': 0,
                        'battery_id': 0,
                        'soc': None,
                        'soh': None
                        }
           }

TREND = {'database': _DATABASE,
         'website': _WEBSITE,
         'hour_graph': '/tmp/lektrix/site/img/lex_pasthours',
         'day_graph': '/tmp/lektrix/site/img/lex_pastdays',
         'month_graph': '/tmp/lektrix/site/img/lex_pastmonths',
         'year_graph': '/tmp/lektrix/site/img/lex_pastyears',
         'yg_vs_month': '/tmp/lektrix/site/img/lex_vs_month',
         'yg_gauge': '/tmp/lektrix/site/img/lex_gauge'
         }

KAMSTRUP = {'database': _DATABASE,
            'sql_table': "mains",
            'sql_command': "INSERT INTO mains ("
                           "sample_time, sample_epoch, "
                           "T1in, T2in, powerin, "
                           "T1out, T2out, powerout, "
                           "tarif, swits"
                           ");"
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            'report_interval': 900,
            'samplespercycle': 88,  # meter runs at 1 telegram every ~10s
            'delay': 0,
            'template': {'sample_time': "dd-mmm-yyyy hh:mm:ss",
                         'sample_epoch': 0,
                         'T1in': 0,
                         'T2in': 0,
                         'powerin': 0,
                         'T1out': 0,
                         'T2out': 0,
                         'powerout': 0,
                         'tarif': 1,
                         'swits': 1
                         }
            }

SOLAREDGE = {'database': _DATABASE,
             'sql_table': "production",
             'sql_command': "INSERT INTO production ("
                            "sample_time, sample_epoch, site_id, energy"
                            ");"
                            "VALUES (?, ?, ?, ?)",
             'report_interval': 900,  # quarter of an hour resolution
             'samplespercycle': 1,
             'delay': 360,
             'director': "https://monitoringapi.solaredge.com",
             'template': {'sample_time': "yyyy-mm-dd hh:mm:ss",
                          'sample_epoch': 0,
                          'site_id': 0,
                          'energy': 0
                          }
             }

ZAPPI = {'database': _DATABASE,
         'sql_table': "charger",
         'sql_command': "INSERT INTO charger ("
                        "sample_time, sample_epoch, site_id,"
                        "exp, gen, gep, imp, h1b, h1d,"
                        "v1, frq"
                        ");"
                        "VALUES (?, ?, ?,"
                        "?, ?, ?, ?, ?, ?,"
                        "?, ?"
                        ")",
         'report_interval': 900,  # 3599,
         'samplespercycle': 1,
         'delay': 180,
         'director': "https://director.myenergi.net",
         'template': {'sample_time': "yyyy-mm-dd hh:mm:ss",
                      'sample_epoch': 0,
                      'site_id': 4.1,
                      'hr': 0,
                      'min': 0,
                      # 'dow': "Mon",
                      'dom': 1,
                      'mon': 8,
                      'yr': 2021,
                      'exp': 0,
                      'gen': 0,
                      'gep': 0,
                      'imp': 0,
                      'h1b': 0,
                      'h1d': 0,
                      'v1': 0,
                      # 'pect1': 0,
                      # 'pect2': 0,
                      # 'pect3': 0,
                      # 'nect1': 0,
                      # 'nect2': 0,
                      # 'nect3': 0,
                      'frq': 0
                      },
         'template_keys_to_drop': ['yr', 'mon', 'dom', 'hr', 'min']
         }
