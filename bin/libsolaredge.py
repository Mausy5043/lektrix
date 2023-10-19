#!/usr/bin/env python3

"""Library functions for SolarEdge."""

import datetime as dt
import functools
import time
from itertools import tee

import dateutil.parser as dtparse
import dateutil.rrule as dtrule
import pytz
import requests

import constants

BASEURL = constants.SOLAREDGE["director"]


class Solaredge:
    """
    Object containing SolarEdge's site API-methods, and some functions that return Pandas DataFrames
    See https://www.solaredge.com/sites/default/files/se_monitoring_api.pdf
    """

    def __init__(self, api_token):
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
                rq_response = requests.get(
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
    def get_list(
        self,
        size=100,
        start_index=0,
        search_text="",
        sort_property="",
        sort_order="ASC",
        status="Active,Pending",
    ):
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
    def get_details(self, site_id):
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
    def get_data_period(self, site_id):
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

    def get_data_period_parsed(self, site_id):
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
        import pandas as pd  # noqa

        j = self.get_data_period(site_id=site_id)
        tz = self.get_timezone(site_id=site_id)
        start, end = [pd.Timestamp(j["dataPeriod"][param]) for param in ["startDate", "endDate"]]
        start, end = start.tz_localize(tz), end.tz_localize(tz)
        return start, end

    def get_energy(self, site_id, start_date, end_date, time_unit="DAY"):
        url = urljoin(BASEURL, "site", site_id, "energy")
        params = {
            "api_key": self.token,
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
        }

        rj = self.request_get_json(url, params)
        return rj

    def get_time_frame_energy(self, site_id, start_date, end_date, time_unit="DAY"):
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

    def get_power(self, site_id, start_time, end_time):
        url = urljoin(BASEURL, "site", site_id, "power")
        params = {
            "api_key": self.token,
            "startTime": start_time,
            "endTime": end_time,
        }

        rj = self.request_get_json(url, params)
        return rj

    def get_overview(self, site_id):
        r = None
        url = urljoin(BASEURL, "site", site_id, "overview")
        params = {"api_key": self.token}

        rj = self.request_get_json(url, params)
        return rj

    def get_power_details(self, site_id, start_time, end_time, meters=None):
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

    def get_energy_details(self, site_id, start_time, end_time, meters=None, time_unit="DAY"):
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
            options: any combination of PRODUCTION, CONSUMPTION, SELFCONSUMPTION, FEEDIN, PURCHASED
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

    # def get_energy_details_dataframe(self, site_id, start_time, end_time, meters=None, time_unit="DAY"):
    #   """
    #   Request Energy Details for a certain site and timeframe as a Pandas DataFrame
    #
    #   Parameters
    #   ----------
    #   site_id : int
    #   start_time : str | dt.date | dt.datetime
    #       Can be any date or datetime object (also pandas.Timestamp)
    #       Timezone-naive objects will be treated as local time at the site
    #   end_time : str | dt.date | dt.datetime
    #       See `start_time`
    #   meters : [str]
    #       default None
    #       list with any combination of these terms: PRODUCTION, CONSUMPTION, SELFCONSUMPTION, FEEDIN, PURCHASED
    #   time_unit : str
    #       default DAY
    #       options: QUARTER_OF_AN_HOUR, HOUR, DAY, WEEK, MONTH, YEAR
    #       Note that this method works around the usage restrictions by requesting chunks of data
    #
    #   Returns
    #   -------
    #   pandas.DataFrame
    #   """
    #   from .parsers import parse_energydetails
    #   import pandas as pd
    #
    #   tz = self.get_timezone(site_id=site_id)
    #   if meters:
    #     meters = ','.join(meters)
    #
    #   # use a generator to do some lazy loading and to (hopefully) save some memory
    #   # when requesting large periods of time
    #   def generate_frames():
    #     # work around the usage restrictions by creating intervals to request data in
    #     for start, end in self.intervalize(time_unit=time_unit, start=start_time, end=end_time):
    #       # format start and end in the correct string notation
    #       start, end = [self._fmt_date(date_obj=time, fmt='%Y-%m-%d %H:%M:%S', tz=tz) for time in [start, end]]
    #       j = self.get_energy_details(site_id=site_id, start_time=start, end_time=end, meters=meters,
    #                                   time_unit=time_unit)
    #       frame = parse_energydetails(j)
    #       yield frame
    #
    #   frames = generate_frames()
    #   df = pd.concat(frames)
    #   df = df.drop_duplicates()
    #   df = df.tz_localize(tz)
    #   return df

    def get_current_power_flow(self, site_id):
        url = urljoin(BASEURL, "site", site_id, "currentPowerFlow")
        params = {"api_key": self.token}

        rj = self.request_get_json(url, params)
        return rj

    def get_storage_data(self, site_id, start_time, end_time, serials=None):
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

    def get_inventory(self, site_id):
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

    @staticmethod
    def intervalize(time_unit, start, end):
        """
        Create pairs of start and end with regular intervals, to deal with usage restrictions on the API
        e.g. requests with `time_unit="DAY"` are limited to 1 year, so when `start` and `end` are more
        than 1 year apart, pairs of timestamps will be generated that respect this limit.

        Args:
            time_unit(str): string can be QUARTER_OF_AN_HOUR, HOUR, DAY, WEEK, MONTH, YEAR
            start (dt.datetime | pd.Timestamp): timestamp of start
            end (dt.datetime | pd.Timestamp): timestamp of end

        Returns:
            ((pd.Timestamp, pd.Timestamp))
        """
        import pandas as pd  # noqa

        if time_unit in {"WEEK", "MONTH", "YEAR"}:
            # no restrictions, so just return start and end
            return [(start, end)]
        if time_unit == "DAY":
            rule = dtrule.YEARLY
        elif time_unit in {"QUARTER_OF_AN_HOUR", "HOUR"}:
            rule = dtrule.MONTHLY
        else:
            raise ValueError(
                "Unknown interval: {}. Choose from QUARTER_OF_AN_HOUR, HOUR, DAY, WEEK, MONTH, YEAR"
            )

        res = []
        for day in dtrule.rrule(rule, dtstart=start, until=end):
            res.append(pd.Timestamp(day))
        res.append(end)
        res = sorted(set(res))
        res = pairwise(res)
        return res


def urljoin(*parts):
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
    url = "/".join(part_list)
    return url


def pairwise(iterable):
    """Create pairs to iterate over.
        eg. [A, B, C, D] -> ([A, B], [B, C], [C, D])

    Parameters
    ----------
    iterable : iterable

    Returns
    -------
    iterable
    """
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)
