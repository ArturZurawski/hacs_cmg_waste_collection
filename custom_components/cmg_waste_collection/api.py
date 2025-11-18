"""API client for Waste Collection."""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import requests

from .const import BASE_URL

_LOGGER = logging.getLogger(__name__)


class WasteCollectionAPI:
    """API client for waste collection schedule."""

    def __init__(self, debug: bool = False):
        """Initialize the API client."""
        self.session = requests.Session()
        self._schedule_cache = None
        self._descriptions_cache = None
        self.debug = debug

    def _post_form(self, url: str, data: dict) -> requests.Response:
        """Send multipart/form-data request."""
        if self.debug:
            _LOGGER.debug("=" * 80)
            _LOGGER.debug("POST REQUEST TO: %s", url)
            _LOGGER.debug("REQUEST DATA: %s", data)

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

        response = self.session.post(url, data=body.encode('utf-8'), headers=headers)

        if self.debug:
            _LOGGER.debug("RESPONSE STATUS: %s", response.status_code)
            try:
                _LOGGER.debug("RESPONSE JSON: %s", response.json())
            except Exception:
                _LOGGER.debug("RESPONSE TEXT: %s", response.text[:500])
            _LOGGER.debug("=" * 80)

        return response

    def get_towns(self, community_id: str) -> List[Dict[str, Any]]:
        """Get list of towns for community."""
        try:
            url = f"{BASE_URL}/townsForCommunity"
            params = {'communityId': community_id}

            if self.debug:
                _LOGGER.debug("=" * 80)
                _LOGGER.debug("GET REQUEST TO: %s", url)
                _LOGGER.debug("REQUEST PARAMS: %s", params)

            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if self.debug:
                _LOGGER.debug("RESPONSE STATUS: %s", resp.status_code)
                _LOGGER.debug("RESPONSE JSON: %s", data)
                _LOGGER.debug("=" * 80)

            if data.get('success'):
                return data['data']['towns']
            return []

        except requests.RequestException as err:
            _LOGGER.error("Error fetching towns: %s", err)
            raise

    def get_schedule_periods(self, community_id: str) -> List[Dict[str, Any]]:
        """Get list of schedule periods for community."""
        try:
            url = f"{BASE_URL}/schedulePeriodsWithDataForCommunity"
            params = {'communityId': community_id}

            if self.debug:
                _LOGGER.debug("=" * 80)
                _LOGGER.debug("GET REQUEST TO: %s", url)
                _LOGGER.debug("REQUEST PARAMS: %s", params)

            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if self.debug:
                _LOGGER.debug("RESPONSE STATUS: %s", resp.status_code)
                _LOGGER.debug("RESPONSE JSON: %s", data)
                _LOGGER.debug("=" * 80)

            if data.get('success'):
                return data['data']['schedulePeriods']
            return []

        except requests.RequestException as err:
            _LOGGER.error("Error fetching schedule periods: %s", err)
            raise

    def get_current_period(self, community_id: str) -> Optional[Dict[str, Any]]:
        """Get the current schedule period that contains today's date."""
        try:
            periods = self.get_schedule_periods(community_id)
            today = datetime.now().date()

            if self.debug:
                _LOGGER.debug("Finding current period for date: %s", today)
                _LOGGER.debug("Available periods: %s",
                             [(p['id'], p['startDate'], p['endDate']) for p in periods])

            # Find period that contains today's date
            for period in periods:
                start = datetime.strptime(period['startDate'], '%Y-%m-%d').date()
                end = datetime.strptime(period['endDate'], '%Y-%m-%d').date()

                if start <= today <= end:
                    if self.debug:
                        _LOGGER.debug("Found matching period: %s (%s - %s)",
                                     period['id'], period['startDate'], period['endDate'])
                    return period

            # If no period contains today, find the most recent PAST period
            # (not future period which may not have data yet)
            if periods:
                past_periods = [
                    p for p in periods
                    if datetime.strptime(p['endDate'], '%Y-%m-%d').date() < today
                ]

                if past_periods:
                    # Return most recent past period (highest end date)
                    sorted_past = sorted(
                        past_periods,
                        key=lambda p: datetime.strptime(p['endDate'], '%Y-%m-%d'),
                        reverse=True
                    )
                    if self.debug:
                        _LOGGER.debug("No active period, using most recent past period: %s (%s - %s)",
                                     sorted_past[0]['id'], sorted_past[0]['startDate'],
                                     sorted_past[0]['endDate'])
                    return sorted_past[0]

                # All periods are in the future, use the earliest one
                sorted_future = sorted(
                    periods,
                    key=lambda p: datetime.strptime(p['startDate'], '%Y-%m-%d')
                )
                if self.debug:
                    _LOGGER.debug("All periods are in future, using earliest: %s (%s - %s)",
                                 sorted_future[0]['id'], sorted_future[0]['startDate'],
                                 sorted_future[0]['endDate'])
                return sorted_future[0]

            return None

        except Exception as err:
            _LOGGER.error("Error finding current period: %s", err)
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
    ) -> tuple[List[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """Get building type groups for street.

        Returns:
            Tuple of (groups list, groupId from response, streets list)
        """
        try:
            _LOGGER.debug("Fetching building groups for street_ids=%s, number=%s",
                         choosed_street_ids, number)

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

            if data.get('success') and 'data' in data:
                streets = data['data'].get('streets', [])

                if 'groups' in data['data']:
                    groups_items = data['data']['groups']['items']
                    group_id = data['data']['groups'].get('groupId')

                    _LOGGER.debug("Found %d building groups, groupId=%s, %d streets",
                                 len(groups_items), group_id, len(streets))

                    return groups_items, group_id, streets

            return [], None, []

        except requests.RequestException as err:
            _LOGGER.error("Error fetching building groups: %s", err)
            raise

    def is_street_id_for_specific_building(
        self,
        town_id: str,
        period_id: str,
        street_id: str,
        user_number: str
    ) -> bool:
        """Check if street_id is for a specific building (not user's address).

        Returns True if street_id has a specific number assigned that doesn't match user_number.
        This helps detect when we're using wrong street_id (e.g., church/company instead of residential).
        """
        try:
            streets = self.get_streets(town_id, period_id)

            for street in streets:
                if street.get('id') == street_id:
                    numbers = street.get('numbers', '')
                    # If numbers field is not empty, it's a specific building
                    if numbers and numbers != '':
                        # Check if user's number matches
                        if user_number not in numbers:
                            _LOGGER.warning(
                                "Street ID %s is for specific building(s) '%s' (user has '%s')",
                                street_id, numbers, user_number
                            )
                            return True
            return False

        except Exception as err:
            _LOGGER.debug("Error checking street_id specificity: %s", err)
            return False

    def find_new_street_id(
        self,
        town_id: str,
        period_id: str,
        street_name: str,
        number: str,
        group_name: str,
        old_street_id: str
    ) -> Optional[str]:
        """Try to find new street_id using same process as initial setup.

        Re-queries API like during initialization to find correct street_id
        for the user's address based on their previously selected group.

        Args:
            town_id: Town ID
            period_id: Schedule period ID
            street_name: Street name user selected
            number: Building number user selected
            group_name: Building group/type user selected (e.g., "Zabudowa wielorodzinna")
            old_street_id: Current street_id that may be incorrect

        Returns:
            New street_id if found, None otherwise
        """
        try:
            _LOGGER.info(
                "Re-querying API for street='%s', number='%s', group='%s', old_id='%s'",
                street_name, number, group_name, old_street_id
            )

            # Step 1: Get fresh street list for this town and period
            streets_list = self.get_streets(town_id, period_id)

            # Step 2: Find our street by name
            matching_street = None
            for street in streets_list:
                if street.get('name', '').lower() == street_name.lower():
                    # Prefer general streets (no specific numbers) over specific buildings
                    if not street.get('numbers', ''):
                        matching_street = street
                        break

            if not matching_street:
                _LOGGER.warning("No matching street found for '%s'", street_name)
                return None

            choosed_street_ids = matching_street.get('choosedStreetIds')
            if not choosed_street_ids:
                _LOGGER.warning("No choosedStreetIds for street '%s'", street_name)
                return None

            _LOGGER.debug("Found street with choosedStreetIds: %s", choosed_street_ids)

            # Step 3: Get building groups (same as during initial setup)
            groups, group_id, streets = self.get_building_groups(
                choosed_street_ids,
                number,
                town_id,
                street_name,
                period_id
            )

            # Step 4: Find the group that matches what user originally selected
            if groups:
                _LOGGER.debug("Found %d building groups, looking for '%s'", len(groups), group_name)
                for group in groups:
                    if group.get('name', '').lower() == group_name.lower():
                        new_street_id = group.get('choosedStreetIds')
                        if new_street_id:
                            _LOGGER.info(
                                "Found matching group '%s' with street_id '%s' (was '%s')",
                                group_name, new_street_id, old_street_id
                            )
                            return new_street_id

                # Group name didn't match - try first group as fallback
                _LOGGER.warning("Group '%s' not found, using first group", group_name)
                if groups[0].get('choosedStreetIds'):
                    return groups[0]['choosedStreetIds']

            # No groups - use street ID from streets array (single building type)
            if streets and len(streets) > 0:
                new_street_id = streets[0].get('id')
                if new_street_id:
                    _LOGGER.info(
                        "No groups, using street_id '%s' from streets[0] (was '%s')",
                        new_street_id, old_street_id
                    )
                    return new_street_id

            _LOGGER.warning("Could not find new street_id for %s %s", street_name, number)
            return None

        except Exception as err:
            _LOGGER.error("Error finding new street_id: %s", err, exc_info=True)
            return None

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
            _LOGGER.debug("API request: number=%s, street_id=%s, town_id=%s, street_name=%s, period_id=%s",
                         number, street_id, town_id, street_name, period_id)

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

            _LOGGER.debug("API response success: %s, data keys: %s",
                         data.get('success'),
                         list(data.get('data', {}).keys()) if data.get('data') else 'no data')

            if data.get('data'):
                schedules_count = len(data['data'].get('schedules', []))
                descriptions_count = len(data['data'].get('scheduleDescription', []))
                _LOGGER.debug("API returned: %d schedules, %d descriptions",
                             schedules_count, descriptions_count)

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

        if self.debug:
            _LOGGER.debug("=" * 80)
            _LOGGER.debug("PARSING SCHEDULE DATA")
            _LOGGER.debug("Raw data keys: %s", list(raw_data.keys()))
            _LOGGER.debug("Number of schedules: %d", len(schedules))
            _LOGGER.debug("Number of descriptions: %d", len(descriptions_list))
            if descriptions_list:
                _LOGGER.debug("Descriptions: %s", descriptions_list)
            if schedules:
                _LOGGER.debug("First 3 schedule items: %s", schedules[:3])
            _LOGGER.debug("=" * 80)

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
            _LOGGER.debug("Fetching schedule data for period_id=%s, street_id=%s, number=%s",
                         period_id, street_id, number)
            raw_data = self.get_waste_types(
                number, street_id, town_id, street_name, period_id
            )

            if not raw_data:
                _LOGGER.error("No data received from API")
                raise Exception("Empty response from API")

            _LOGGER.debug("Received raw data, parsing schedule")
            result = self.parse_schedule(raw_data, selected_type_ids)

            # Validate result
            if not result or len(result) != 2:
                _LOGGER.error("Invalid parse_schedule result: %s", result)
                raise Exception("Invalid schedule data format")

            schedule, descriptions = result

            if not schedule or not descriptions:
                # If we have cached data, use it
                if self._schedule_cache and self._descriptions_cache:
                    _LOGGER.info("Empty schedule or descriptions after parsing, using cached data (%d waste types)",
                                  len(self._schedule_cache))
                    return self._schedule_cache, self._descriptions_cache

                # No cached data available - return empty data
                # This signals __init__.py to try finding new street_id (API may have changed IDs)
                _LOGGER.warning("Empty schedule or descriptions after parsing and no cached data available")
                return {}, {}

            _LOGGER.debug("Successfully parsed schedule: %d waste types", len(schedule))
            return schedule, descriptions

        except Exception as err:
            _LOGGER.error("Failed to update schedule: %s", err, exc_info=True)
            # Return cached data if available
            if self._schedule_cache and self._descriptions_cache:
                _LOGGER.warning("API error, using cached schedule data (%d waste types)",
                              len(self._schedule_cache))
                return self._schedule_cache, self._descriptions_cache
            # Return empty data - let caller try to fix the issue
            _LOGGER.warning("No cached data available, returning empty data")
            return {}, {}