"""The Waste Collection integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WasteCollectionAPI
from .const import (
    CONF_COMMUNITY_ID,
    CONF_DEBUG_LOGGING,
    CONF_GROUP_NAME,
    CONF_NUMBER,
    CONF_PERIOD_CHANGE_DATE,
    CONF_PERIOD_END,
    CONF_PERIOD_ID,
    CONF_PERIOD_START,
    CONF_SELECTED_WASTE_TYPES,
    CONF_STREET_CHOOSED_IDS,
    CONF_STREET_ID,
    CONF_STREET_NAME,
    CONF_TOWN_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BUTTON, Platform.CALENDAR]

# This integration is only configured through config entries
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Waste Collection component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Waste Collection from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Configure debug logging if enabled
    debug_logging = entry.options.get(
        CONF_DEBUG_LOGGING,
        entry.data.get(CONF_DEBUG_LOGGING, False)
    )
    if debug_logging:
        logging.getLogger(f"custom_components.{DOMAIN}").setLevel(logging.DEBUG)
        _LOGGER.info("Debug logging enabled for CMG Waste Collection")
    else:
        logging.getLogger(f"custom_components.{DOMAIN}").setLevel(logging.INFO)

    # Get configuration (note: street_id may change when period changes, so we read it from entry.data each time)
    town_id = entry.data[CONF_TOWN_ID]
    community_id = entry.data[CONF_COMMUNITY_ID]
    street_name = entry.data[CONF_STREET_NAME]
    number = entry.data[CONF_NUMBER]

    # Initialize API with debug flag
    api = WasteCollectionAPI(debug=debug_logging)

    # Create coordinator with NO automatic updates
    async def async_update_data():
        """Fetch data from API."""
        try:
            _LOGGER.debug("Starting data update")

            # Always get current period to ensure we use the latest one
            current_period = await hass.async_add_executor_job(
                api.get_current_period,
                community_id
            )

            if not current_period:
                _LOGGER.error("No active schedule period found")
                raise UpdateFailed("No active schedule period found")

            period_id = current_period['id']
            _LOGGER.debug("Using period_id: %s (%s - %s)",
                         period_id,
                         current_period['startDate'],
                         current_period['endDate'])

            # Check if period changed OR manual refresh requested - if so, we need to re-fetch building type
            # Always read current street_id from entry.data (it may have been updated)
            current_street_id = entry.data[CONF_STREET_ID]
            period_changed = period_id != entry.data.get(CONF_PERIOD_ID)
            force_refresh = hass.data[DOMAIN][entry.entry_id].get("force_building_type_refresh", False)

            if period_changed or force_refresh:
                if force_refresh:
                    _LOGGER.info("Manual refresh requested - re-fetching building type and street data")
                    # Reset the flag
                    hass.data[DOMAIN][entry.entry_id]["force_building_type_refresh"] = False

                if period_changed:
                    _LOGGER.info(
                        "Schedule period changed from %s to %s (%s - %s)",
                        entry.data.get(CONF_PERIOD_ID),
                        period_id,
                        current_period['startDate'],
                        current_period['endDate']
                    )

                # Re-fetch street data for new period (or for manual refresh)
                try:
                    _LOGGER.debug("Re-fetching street and building type data for new period")

                    # Get streets for the new period
                    streets = await hass.async_add_executor_job(
                        api.get_streets,
                        town_id,
                        period_id
                    )

                    if not streets:
                        _LOGGER.warning("No streets found for new period, using old street_id")
                    else:
                        # Find our street by name
                        matching_street = None
                        for s in streets:
                            if s.get('name') == street_name:
                                matching_street = s
                                break

                        if not matching_street:
                            _LOGGER.warning("Street '%s' not found in new period, using old street_id", street_name)
                        else:
                            street_choosed_ids = matching_street.get('choosedStreetIds')
                            _LOGGER.debug("Found street '%s' with choosedStreetIds=%s", street_name, street_choosed_ids)

                            # Get building groups for new period
                            groups, group_id, group_streets = await hass.async_add_executor_job(
                                api.get_building_groups,
                                street_choosed_ids,
                                number,
                                town_id,
                                street_name,
                                period_id
                            )

                            # Determine new street_id based on building type
                            if not groups:
                                # No groups - single building type street
                                if group_streets and len(group_streets) > 0:
                                    current_street_id = group_streets[0]['id']
                                    _LOGGER.info("New period: single building type, street_id=%s", current_street_id)
                                else:
                                    current_street_id = street_choosed_ids
                                    _LOGGER.info("New period: using choosedStreetIds=%s as street_id", current_street_id)
                            else:
                                # Multiple groups - find the one matching our saved group name
                                group_name = entry.data.get(CONF_GROUP_NAME)
                                matching_group = None
                                for g in groups:
                                    if g.get('name') == group_name:
                                        matching_group = g
                                        break

                                if matching_group:
                                    current_street_id = matching_group['choosedStreetIds']
                                    _LOGGER.info("New period: matched building type '%s', street_id=%s", group_name, current_street_id)
                                else:
                                    # Group name not found, use first group
                                    current_street_id = groups[0]['choosedStreetIds']
                                    _LOGGER.warning("Building type '%s' not found in new period, using first group street_id=%s", group_name, current_street_id)

                            # Update entry data with new IDs (but not selected_waste_types yet - we need new data first)
                            hass.config_entries.async_update_entry(
                                entry,
                                data={
                                    **entry.data,
                                    CONF_PERIOD_ID: period_id,
                                    CONF_PERIOD_START: current_period['startDate'],
                                    CONF_PERIOD_END: current_period['endDate'],
                                    CONF_PERIOD_CHANGE_DATE: current_period['changeDate'],
                                    CONF_STREET_ID: current_street_id,
                                    CONF_STREET_CHOOSED_IDS: street_choosed_ids,
                                }
                            )
                            _LOGGER.info("Updated entry with new period and street data")

                except Exception as err:
                    _LOGGER.error("Error re-fetching building type for new period: %s", err, exc_info=True)
                    _LOGGER.warning("Continuing with old street_id=%s", current_street_id)

            # Fetch schedule data
            result = await hass.async_add_executor_job(
                api.update,
                number,
                current_street_id,
                town_id,
                street_name,
                period_id,
                None,  # Get all types for individual sensors
            )

            # Validate result
            if not result or not isinstance(result, tuple) or len(result) != 2:
                _LOGGER.error("Invalid result from API: %s", result)
                raise UpdateFailed("Invalid data format from API")

            schedule, descriptions = result

            if not schedule or not descriptions:
                _LOGGER.warning("Empty schedule or descriptions: schedule=%s, descriptions=%s",
                            bool(schedule), bool(descriptions))
                _LOGGER.warning("New period may not have data yet, keeping old data if available")
                # Don't raise error immediately - coordinator will use cached data
                raise UpdateFailed("Empty data received from API - period may not have data yet")

            # If period changed or manual refresh, update selected_waste_types with new IDs
            if period_changed or force_refresh:
                old_selected_ids = entry.options.get(
                    CONF_SELECTED_WASTE_TYPES,
                    entry.data.get(CONF_SELECTED_WASTE_TYPES, [])
                )

                if old_selected_ids:
                    # Get old descriptions to map old ID -> waste name
                    old_data = coordinator.data
                    old_id_to_name = {}
                    if old_data:
                        _, old_descriptions = old_data
                        for waste_name, desc in old_descriptions.items():
                            old_id_to_name[desc.get('id')] = waste_name

                    # Map selected waste names to new IDs
                    selected_names = [old_id_to_name.get(id) for id in old_selected_ids if id in old_id_to_name]
                    new_selected_ids = []
                    for waste_name, desc in descriptions.items():
                        if waste_name in selected_names:
                            new_selected_ids.append(desc.get('id'))

                    if new_selected_ids != old_selected_ids:
                        _LOGGER.info("Updating selected_waste_types: old IDs=%s, new IDs=%s",
                                    old_selected_ids, new_selected_ids)

                        # Update both data and options (sensors will read dynamically)
                        hass.config_entries.async_update_entry(
                            entry,
                            data={
                                **entry.data,
                                CONF_SELECTED_WASTE_TYPES: new_selected_ids,
                            },
                            options={
                                **entry.options,
                                CONF_SELECTED_WASTE_TYPES: new_selected_ids,
                            }
                        )

            _LOGGER.info("Data update successful: %d waste types, %d total dates",
                        len(schedule),
                        sum(len(dates) for dates in schedule.values()))

            return schedule, descriptions

        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.error("Error during data update: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        # NO update_interval - we control updates manually
    )

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "sensor_list": [],  # Will be populated when sensors are created
        "force_building_type_refresh": False,  # Flag for manual refresh
    }

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Schedule daily update at 00:01
    async def daily_update(now):
        """Update data daily at midnight."""
        _LOGGER.info("Daily midnight update triggered")
        await coordinator.async_request_refresh()

    entry.async_on_unload(
        async_track_time_change(hass, daily_update, hour=0, minute=1, second=0)
    )

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok