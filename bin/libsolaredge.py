#!/usr/bin/env python3

# lektrix
# Copyright (C) 2024  Maurice (mausy5043) Hendrix
# AGPL-3.0-or-later  - see LICENSE

"""Library functions for SolarEdge."""

import datetime as dt
import functools
import time

import constants
import dateutil.parser as dtparse
import pandas as pd
import pytz
import requests

BASEURL = constants.SOLAREDGE["director"]


class Solaredge:
    """
    Object containing SolarEdge's site API-methods, and some functions that
    return Pandas DataFrames
    See https://www.solaredge.com/sites/default/files/se_monitoring_api.pdf
    """

    def __init__(self, api_token) -> None:
        """
        To communicate, you need to set an API access token.
        Get it from your account.

        Parameters
        ----------
        api_token : str
        """
        self.token = api_token

    @staticmethod
    def request_get_json(url: str, params: dict) -> dict:
        """Call a URL and return the result as a json dict"""
        rq_json = {}
        retries = 3
        while True:
            try:
                rq_response = requests.get(  # nosec B113
                    url,
                    params,
                    headers={"content-type": "application/json"},
                    timeout=constants.SOLAREDGE["requests_timeout"],
                )
                rq_response.raise_for_status()
                rq_json = rq_response.json()
            except requests.exceptions.RequestException:
                retries -= 1
                if retries:
                    time.sleep(59)
                    continue
                raise
            break

        return rq_json

    @functools.lru_cache(maxsize=128, typed=False)
    def get_list(  # pylint: disable=R0917
        self,
        size=100,
        start_index=0,
        search_text="",
        sort_property="",
        sort_order="ASC",
        status="Active,Pending",
    ) -> dict:
        """
        Request a list of all sites

        Returns:
            dict
        """

        url = urljoin(BASEURL, "sites", "list")

        params = {
            "api_key": self.token,
            "size": size,
            "startIndex": start_index,
            "sortOrder": sort_order,
            "status": status,
        }

        if search_text:
            params["searchText"] = search_text

        if sort_property:
            params["sortProperty"] = sort_property

        rj = self.request_get_json(url, params)
        return rj

    @functools.lru_cache(maxsize=128, typed=False)
    def get_details(self, site_id) -> dict:
        """
        Request details about a certain site

        Args:
        site_id (int): site to get details for.

        Returns:
            dict containing details of site
        """
        url = urljoin(BASEURL, "site", site_id, "details")
        params = {"api_key": self.token}

        rj = self.request_get_json(url, params)
        return rj

    @functools.lru_cache(maxsize=128, typed=False)
    def get_data_period(self, site_id) -> dict:
        """
        Request the dataperiod for a certain site.
        This returns the start and end dates for which there
        is data available.

        Use `get_data_period_parsed` to get the dates as datetime objects

        Parameters
        ----------
        site_id : int

        Returns
        -------
        dict
        """
        url = urljoin(BASEURL, "site", site_id, "dataPeriod")
        params = {"api_key": self.token}

        rj = self.request_get_json(url, params)
        return rj

    def get_data_period_parsed(self, site_id) -> tuple:
        """
        Request the data period for a certain site.
        This returns the start and end dates for which there
        is data available, as datetime objects

        Parameters
        ----------
        site_id : int

        Returns
        -------
        (pd.Timestamp, pd.Timestamp)
        """

        j = self.get_data_period(site_id=site_id)
        tz = self.get_timezone(site_id=site_id)
        start, end = [pd.Timestamp(j["dataPeriod"][param]) for param in ["startDate", "endDate"]]
        start, end = start.tz_localize(tz), end.tz_localize(tz)
        return start, end

    def get_energy(self, site_id, start_date, end_date, time_unit="DAY") -> dict:
        url = urljoin(BASEURL, "site", site_id, "energy")
        params = {
            "api_key": self.token,
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
        }

        rj = self.request_get_json(url, params)
        return rj

    def get_time_frame_energy(self, site_id, start_date, end_date, time_unit="DAY") -> dict:
        # BEWARE: only date NO TIME
        url = urljoin(BASEURL, "site", site_id, "timeFrameEnergy")
        params = {
            "api_key": self.token,
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
        }

        rj = self.request_get_json(url, params)
        return rj

    def get_power(self, site_id, start_time, end_time) -> dict:
        url = urljoin(BASEURL, "site", site_id, "power")
        params = {
            "api_key": self.token,
            "startTime": start_time,
            "endTime": end_time,
        }

        rj = self.request_get_json(url, params)
        return rj

    def get_overview(self, site_id) -> dict:
        url = urljoin(BASEURL, "site", site_id, "overview")
        params = {"api_key": self.token}

        rj = self.request_get_json(url, params)
        return rj

    def get_power_details(self, site_id, start_time, end_time, meters=None) -> dict:
        url = urljoin(BASEURL, "site", site_id, "powerDetails")
        params = {
            "api_key": self.token,
            "startTime": start_time,
            "endTime": end_time,
        }

        if meters:
            params["meters"] = meters

        rj = self.request_get_json(url, params)
        return rj

    def get_energy_details(  # pylint: disable=R0917
        self, site_id, start_time, end_time, meters=None, time_unit="DAY"
    ) -> dict:
        """
        Request Energy Details for a specific site and timeframe

        Use `get_energy_details_dataframe` to get the result as a Pandas DataFrame

        Parameters
        ----------
        site_id : int
        start_time : str
            needs to have the format '%Y-%m-%d %H:%M:%S' ("2018-02-15 10:00:00")
        end_time : str
            see `start_time
        meters : str
            default None
            options: any combination of
                PRODUCTION, CONSUMPTION, SELFCONSUMPTION, FEEDIN, PURCHASED
                separated by a comma. eg: "PRODUCTION,CONSUMPTION"
        time_unit : str
            default DAY
            options: QUARTER_OF_AN_HOUR, HOUR, DAY, WEEK, MONTH, YEAR
            Note that QUARTER_OF_AN_HOUR and HOUR are restricted to one month of data,
            DAY is restricted to one year of data, the others are unrestricted

        Returns
        -------
        dict
        """
        url = urljoin(BASEURL, "site", site_id, "energyDetails")
        params = {
            "api_key": self.token,
            "startTime": start_time,
            "endTime": end_time,
            "timeUnit": time_unit,
        }

        if meters:
            params["meters"] = meters

        rj = self.request_get_json(url, params)
        return rj

    def get_current_power_flow(self, site_id) -> dict:
        url = urljoin(BASEURL, "site", site_id, "currentPowerFlow")
        params = {"api_key": self.token}

        rj = self.request_get_json(url, params)
        return rj

    def get_storage_data(self, site_id, start_time, end_time, serials=None) -> dict:
        url = urljoin(BASEURL, "site", site_id, "storageData")
        params = {
            "api_key": self.token,
            "startTime": start_time,
            "endTime": end_time,
        }

        if serials:
            params["serials"] = serials.join(",")

        rj = self.request_get_json(url, params)
        return rj

    def get_inventory(self, site_id) -> dict:
        url = urljoin(BASEURL, "site", site_id, "inventory")
        params = {"api_key": self.token}

        rj = self.request_get_json(url, params)
        return rj

    def get_timezone(self, site_id):
        """
        Get the timezone of a certain site (eg. 'Europe/Brussels')

        Parameters
        ----------
        site_id : int

        Returns
        -------
        str
        """
        details = self.get_details(site_id=site_id)
        tz = details["details"]["location"]["timeZone"]
        return tz

    @staticmethod
    def _fmt_date(date_obj, fmt, tz=None):
        """
        Convert any input to a valid datestring of format
        If you pass a localized datetime, it is converted to tz first

        Parameters
        ----------
        date_obj : str | dt.date | dt.datetime

        Returns
        -------
        str
        """
        if isinstance(date_obj, str):
            try:
                dt.datetime.strptime(date_obj, fmt)
            except ValueError:
                date_obj = dtparse.parse(date_obj)
            else:
                return date_obj
        if hasattr(date_obj, "tzinfo") and date_obj.tzinfo is not None:
            if tz is None:
                raise ValueError("Please supply a target timezone")
            _tz = pytz.timezone(tz)
            date_obj = date_obj.astimezone(_tz)

        return date_obj.strftime(fmt)

    # @staticmethod
    # def intervalize(time_unit, start, end):
    #     """
    #     Create pairs of start and end with regular intervals, to deal with usage
    #     restrictions on the API.
    #     e.g. requests with `time_unit="DAY"` are limited to 1 year, so when `start` and `end`
    # are more than 1 year apart, pairs of timestamps will be generated that
    # respect this limit.

    #     Args:
    #         time_unit(str): string can be QUARTER_OF_AN_HOUR, HOUR, DAY, WEEK, MONTH, YEAR
    #         start (dt.datetime | pd.Timestamp): timestamp of start
    #         end (dt.datetime | pd.Timestamp): timestamp of end

    #     Returns:
    #         ((pd.Timestamp, pd.Timestamp))
    #     """

    #     if time_unit in {"WEEK", "MONTH", "YEAR"}:
    #         # no restrictions, so just return start and end
    #         return [(start, end)]
    #     if time_unit == "DAY":
    #         rule = dtrule.YEARLY
    #     elif time_unit in {"QUARTER_OF_AN_HOUR", "HOUR"}:
    #         rule = dtrule.MONTHLY
    #     else:
    #         raise ValueError(
    #             "Unknown interval: {}. Choose from QUARTER_OF_AN_HOUR, HOUR, "
    #             "DAY, WEEK, MONTH, YEAR"
    #         )

    #     res = []
    #     for day in dtrule.rrule(rule, dtstart=start, until=end):
    #         res.append(pd.Timestamp(day))
    #     res.append(end)
    #     res = sorted(set(res))
    #     res = pairwise(res)
    #     return res


def urljoin(*parts) -> str:
    """Join terms together with forward slashes.

    Parameters
    ----------
    parts

    Returns
    -------
    str
    """
    # first strip extra forward slashes (except http:// and the likes) and
    # create list
    part_list = []
    for part in parts:
        p = str(part)
        if p.endswith("//"):
            p = p[0:-1]
        else:
            p = p.strip("/")
        part_list.append(p)
    # join everything together
    url: str = "/".join(part_list)
    return url


# def pairwise(iterable) -> zip:
#     """Create pairs to iterate over.
#         eg. [A, B, C, D] -> ([A, B], [B, C], [C, D])

#     Parameters
#     ----------
#     iterable : iterable

#     Returns
#     -------
#     iterable
#     """
#     a, b = tee(iterable)
#     next(b, None)
#     return zip(a, b)
