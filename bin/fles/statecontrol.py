#!/usr/bin/env python3

import base64

import flask
from fles import app  # noqa
from fles import kratlib  # noqa

KRAT = kratlib.Fles()


@app.route("/", methods=['GET', 'POST'])
@app.route("/state", methods=['GET', 'POST'])
def state():
    global KRAT
    if flask.request.method == 'POST':
        pass

    if flask.request.method == 'GET':
        pass

    hour_m_img = "".join(["data:image/png;base64,",
                          str(base64.b64encode(open("/tmp/lektrix/site/img/lex_pasthours_mains.png",
                                                    "rb"
                                                    ).read()))[2:-1]
                          ])
    day_m_img = "".join(["data:image/png;base64,",
                         str(base64.b64encode(open("/tmp/lektrix/site/img/lex_pastdays_mains.png",
                                                   "rb"
                                                   ).read()))[2:-1]
                         ])
    month_m_img = "".join(["data:image/png;base64,",
                           str(base64.b64encode(open("/tmp/lektrix/site/img/lex_pastmonths_mains.png",
                                                     "rb").read()))[2:-1]
                           ])
    year_m_img = "".join(["data:image/png;base64,",
                          str(base64.b64encode(open("/tmp/lektrix/site/img/lex_pastyears_mains.png",
                                                    "rb"
                                                    ).read()))[2:-1]
                          ])
    zappi_img = "".join(["data:image/png;base64,",
                         str(base64.b64encode(open("/tmp/lektrix/site/img/zap_pastday.png",
                                                   "rb").read()))[2:-1]
                         ])
    balance_img = "".join(["data:image/png;base64,",
                           str(base64.b64encode(open("/tmp/lektrix/site/img/lex_gauge.png",
                                                     "rb").read()))[2:-1]
                           ])
    year_trend_img = "".join(["data:image/png;base64,",
                              str(base64.b64encode(open("/tmp/lektrix/site/img/lex_pastyear_mains.png",
                                                        "rb").read()))[2:-1]
                              ])
    year_sum_img = "".join(["data:image/png;base64,",
                            str(base64.b64encode(open("/tmp/lektrix/site/img/lex_vs_year.png",
                                                      "rb").read()))[2:-1]
                            ])
    year_cmp_img = "".join(["data:image/png;base64,",
                            str(base64.b64encode(open("/tmp/lektrix/site/img/lex_vs_month.png",
                                                      "rb").read()))[2:-1]
                            ])
    # gld = KRAT.get_latest_data('volt_bat, load_ups, charge_bat')
    return flask.render_template('state.html',
                                 t1_in="n/a",  # f"{gld[0]:.1f} \u00B0C",
                                 t2_in="n/a",  # f"{gld[0]:.1f} \u00B0C",
                                 t1_out="n/a",  # f"{gld[0]:.1f} \u00B0C",
                                 t2_out="n/a",  # f"{gld[0]:.1f} \u00B0C",
                                 hour_m_img=hour_m_img,
                                 day__m_img=day_m_img,
                                 month_m_img=month_m_img,
                                 year_m_img=year_m_img,
                                 zappi_img=zappi_img,
                                 balance_img=balance_img,
                                 year_trend_img=year_trend_img,
                                 year_sum_img=year_sum_img,
                                 year_cmp_img=year_cmp_img
                                 )
