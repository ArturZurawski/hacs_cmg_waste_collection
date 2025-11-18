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
    CONF_NUMBER,
    CONF_PERIOD_ID,
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

    # Get configuration
    town_id = entry.data[CONF_TOWN_ID]
    community_id = entry.data[CONF_COMMUNITY_ID]
    street_name = entry.data[CONF_STREET_NAME]
    street_id = entry.data[CONF_STREET_ID]
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

            # Log if period changed
            old_period_id = entry.data.get(CONF_PERIOD_ID)
            if period_id != old_period_id:
                _LOGGER.info(
                    "Schedule period changed from %s to %s (%s - %s)",
                    old_period_id,
                    period_id,
                    current_period['startDate'],
                    current_period['endDate']
                )

            # Fetch schedule data
            result = await hass.async_add_executor_job(
                api.update,
                number,
                street_id,
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

            # If API returns empty data, try to find new street_id
            # (API sometimes changes street IDs between periods)
            if not schedule or not descriptions:
                _LOGGER.warning(
                    "Empty schedule/descriptions for street_id=%s. API may have changed street IDs.",
                    street_id
                )

                # Try to find new street_id for this street and number
                new_street_id = await hass.async_add_executor_job(
                    api.find_new_street_id,
                    town_id,
                    period_id,
                    street_name,
                    number,
                    street_id
                )

                if new_street_id and new_street_id != street_id:
                    _LOGGER.info(
                        "Found new street_id '%s' (was '%s'), updating configuration",
                        new_street_id, street_id
                    )

                    # Update config_entry with new street_id
                    new_data = dict(entry.data)
                    new_data[CONF_STREET_ID] = new_street_id
                    hass.config_entries.async_update_entry(entry, data=new_data)

                    # Retry with new street_id
                    street_id = new_street_id
                    result = await hass.async_add_executor_job(
                        api.update,
                        number,
                        street_id,
                        town_id,
                        street_name,
                        period_id,
                        None,
                    )

                    if result and isinstance(result, tuple) and len(result) == 2:
                        schedule, descriptions = result

            if not schedule or not descriptions:
                _LOGGER.error(
                    "No waste collection data available for %s %s (street_id=%s, period=%s)",
                    street_name, number, street_id, period_id
                )
                _LOGGER.error(
                    "You may need to reconfigure this integration. "
                    "Go to Settings → Devices & Services → CMG Waste Collection and delete/re-add."
                )
                # Don't raise error immediately - coordinator will use cached data
                raise UpdateFailed("No waste collection data available - reconfiguration may be needed")

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