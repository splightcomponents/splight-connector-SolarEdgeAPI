import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, TypeVar, Union

import requests
from splight_lib.logging import getLogger

logger = getLogger()


class SolarEdgeAPIClient:
    _BASE_URL = "https://monitoringapi.solaredge.com"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def get_power(self, site_id: str, start_time: datetime, end_time: datetime) -> Dict:
        url = f"{self._BASE_URL}/site/{site_id}/power/"

        start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

        params = {
            "api_key": self._api_key,
            "startTime": start_time_str,
            "endTime": end_time_str,
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            return {}

    def get_energy(
        self, site_id: str, start_date: datetime, end_date: datetime
    ) -> Dict:
        url = f"{self._BASE_URL}/site/{site_id}/energy/"

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        params = {
            "api_key": self._api_key,
            "startDate": start_date_str,
            "endDate": end_date_str,
            "timeUnit": "QUARTER_OF_AN_HOUR",
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            return {}

    def get_inverter_data(
        self, site_id: str, inverter_id: str, start_date: datetime, end_date: datetime
    ) -> Dict:
        url = f"{self._BASE_URL}/site/{site_id}/energy/"

        params = {
            "api_key": self._api_key,
            "startTime": start_date,
            "endTime": end_date,
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            return {}


# client.get_energy(site_id=...)
