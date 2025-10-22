"""API client for Waste Collection."""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import requests

from .const import BASE_URL

_LOGGER = logging.getLogger(__name__)


class WasteCollectionAPI:
    """API client for waste collection schedule."""

    def __init__(self):
        """Initialize the API client."""
        self.session = requests.Session()
        self._schedule_cache = None
        self._descriptions_cache = None

    def _post_form(self, url: str, data: dict) -> requests.Response:
        """Send multipart/form-data request."""
        boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
        body = ''.join([
            f'------{boundary}\r\n'
            f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
            for k, v in data.items()
        ]) + f'------{boundary}--\r\n'

        headers = {
            'Content-Type': f'multipart/form-data; boundary=----{boundary}',
            'Origin': 'https://pluginv1.dtsolution.pl',
        }

        return self.session.post(url, data=body.encode('utf-8'), headers=headers)

    def get_towns(self, community_id: str) -> List[Dict[str, Any]]:
        """Get list of towns for community."""
        try:
            resp = self.session.get(
                f"{BASE_URL}/townsForCommunity",
                params={'communityId': community_id},
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get('success'):
                return data['data']['towns']
            return []

        except requests.RequestException as err:
            _LOGGER.error("Error fetching towns: %s", err)
            raise

    def get_schedule_periods(self, community_id: str) -> List[Dict[str, Any]]:
        """Get list of schedule periods for community."""
        try:
            resp = self.session.get(
                f"{BASE_URL}/schedulePeriodsWithDataForCommunity",
                params={'communityId': community_id},
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get('success'):
                periods = data['data']['schedulePeriods']
                # Filter by current year
                current_year = str(datetime.now().year)
                return [
                    p for p in periods
                    if p['startDate'].startswith(current_year)
                ]
            return []

        except requests.RequestException as err:
            _LOGGER.error("Error fetching schedule periods: %s", err)
            raise

    def get_streets(self, town_id: str, period_id: str) -> List[Dict[str, Any]]:
        """Get list of streets for town."""
        try:
            resp = self._post_form(f"{BASE_URL}/streetsForTown", {
                'townId': town_id,
                'periodId': period_id
            })
            resp.raise_for_status()
            data = resp.json()

            if data.get('success'):
                return data['data']
            return []

        except requests.RequestException as err:
            _LOGGER.error("Error fetching streets: %s", err)
            raise

    def get_building_groups(
        self,
        choosed_street_ids: str,
        number: str,
        town_id: str,
        street_name: str,
        period_id: str
    ) -> List[Dict[str, Any]]:
        """Get building type groups for street."""
        try:
            resp = self._post_form(f"{BASE_URL}/streets", {
                'choosedStreetIds': choosed_street_ids,
                'number': number,
                'townId': town_id,
                'streetName': street_name,
                'schedulePeriodId': period_id,
                'groupId': '1'
            })
            resp.raise_for_status()
            data = resp.json()

            if data.get('success') and 'groups' in data['data']:
                return data['data']['groups']['items']
            return []

        except requests.RequestException as err:
            _LOGGER.error("Error fetching building groups: %s", err)
            raise

    def get_waste_types(
        self,
        number: str,
        street_id: str,
        town_id: str,
        street_name: str,
        period_id: str
    ) -> Dict[str, Any]:
        """Get waste types and schedule for location."""
        try:
            resp = self._post_form(f"{BASE_URL}/schedules", {
                'number': number,
                'streetId': street_id,
                'townId': town_id,
                'streetName': street_name,
                'schedulePeriodId': period_id,
                'lng': 'pl'
            })
            resp.raise_for_status()
            data = resp.json()

            if data.get('success'):
                return data['data']
            return {}

        except requests.RequestException as err:
            _LOGGER.error("Error fetching waste types: %s", err)
            raise

    def parse_schedule(
        self,
        raw_data: Dict[str, Any],
        selected_type_ids: Optional[List[str]] = None
    ) -> tuple[Dict[str, List[datetime]], Dict[str, Dict[str, Any]]]:
        """Parse schedule data into structured format."""
        schedules = raw_data.get('schedules', [])
        descriptions_list = raw_data.get('scheduleDescription', [])

        _LOGGER.debug("Parsing %d schedules and %d descriptions", len(schedules), len(descriptions_list))

        # Build descriptions dict - map by id
        descriptions_by_id = {}
        for desc in descriptions_list:
            waste_id = desc.get('id', '')
            waste_name = desc.get('name', '').strip()
            if waste_id and waste_name:
                descriptions_by_id[waste_id] = {
                    'name': waste_name,
                    'color': desc.get('color', '#000000'),
                    'description': desc.get('description', ''),
                    'type_id': desc.get('typeId', ''),
                    'order': desc.get('order', '999'),
                }

        _LOGGER.debug("Found %d waste type descriptions", len(descriptions_by_id))

        # Build schedule from schedules array
        waste_schedule = {}
        for schedule_item in schedules:
            desc_id = schedule_item.get('scheduleDescriptionId', '')

            if desc_id not in descriptions_by_id:
                continue

            waste_name = descriptions_by_id[desc_id]['name']

            if waste_name not in waste_schedule:
                waste_schedule[waste_name] = []

            # Parse dates
            month = schedule_item.get('month')
            year = schedule_item.get('year')
            days = schedule_item.get('days', '')

            if month and year and days:
                try:
                    month_int = int(month)
                    year_int = int(year)

                    for day_str in str(days).split(';'):
                        day_str = day_str.strip()
                        if day_str:
                            try:
                                day_int = int(day_str)
                                date = datetime(year_int, month_int, day_int)
                                waste_schedule[waste_name].append(date)
                            except (ValueError, TypeError) as e:
                                _LOGGER.warning("Failed to parse date: %s/%s/%s - %s", year, month, day_str, e)
                except (ValueError, TypeError) as e:
                    _LOGGER.warning("Failed to parse month/year: %s/%s - %s", year, month, e)

        # Sort dates and remove duplicates
        for waste_name in waste_schedule:
            waste_schedule[waste_name] = sorted(set(waste_schedule[waste_name]))
            _LOGGER.debug("Waste type '%s': %d dates from %s to %s",
                         waste_name,
                         len(waste_schedule[waste_name]),
                         waste_schedule[waste_name][0].strftime("%Y-%m-%d") if waste_schedule[waste_name] else "N/A",
                         waste_schedule[waste_name][-1].strftime("%Y-%m-%d") if waste_schedule[waste_name] else "N/A")

        # Build final descriptions dict (only for types we have schedules for)
        descriptions = {}
        for waste_name in waste_schedule:
            # Find the description by matching name
            for desc_id, desc_data in descriptions_by_id.items():
                if desc_data['name'] == waste_name:
                    descriptions[waste_name] = {
                        'id': desc_id,
                        'color': desc_data['color'],
                        'description': desc_data['description'],
                        'type_id': desc_data['type_id'],
                        'order': desc_data['order'],
                    }
                    break

        # Filter selected types if provided
        if selected_type_ids:
            descriptions = {
                k: v for k, v in descriptions.items()
                if v['id'] in selected_type_ids
            }
            waste_schedule = {
                k: v for k, v in waste_schedule.items()
                if k in descriptions
            }
            _LOGGER.debug("Filtered to %d selected waste types", len(descriptions))

        self._schedule_cache = waste_schedule
        self._descriptions_cache = descriptions

        _LOGGER.info("Parsed %d waste types with total %d collection dates",
                    len(waste_schedule),
                    sum(len(dates) for dates in waste_schedule.values()))

        return waste_schedule, descriptions

    def update(
        self,
        number: str,
        street_id: str,
        town_id: str,
        street_name: str,
        period_id: str,
        selected_type_ids: Optional[List[str]] = None
    ) -> tuple[Dict[str, List[datetime]], Dict[str, Dict[str, Any]]]:
        """Fetch and return updated schedule."""
        try:
            _LOGGER.debug("Fetching schedule data")
            raw_data = self.get_waste_types(
                number, street_id, town_id, street_name, period_id
            )
            return self.parse_schedule(raw_data, selected_type_ids)

        except Exception as err:
            _LOGGER.error("Failed to update schedule: %s", err)
            # Return cached data if available
            if self._schedule_cache and self._descriptions_cache:
                _LOGGER.warning("Using cached schedule data")
                return self._schedule_cache, self._descriptions_cache
            raise