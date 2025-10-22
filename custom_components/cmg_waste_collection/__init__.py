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
    CONF_NUMBER,
    CONF_PERIOD_ID,
    CONF_STREET_ID,
    CONF_STREET_NAME,
    CONF_TOWN_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BUTTON]

# This integration is only configured through config entries
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Waste Collection component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Waste Collection from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Get configuration
    town_id = entry.data[CONF_TOWN_ID]
    period_id = entry.data[CONF_PERIOD_ID]
    street_name = entry.data[CONF_STREET_NAME]
    street_id = entry.data[CONF_STREET_ID]
    number = entry.data[CONF_NUMBER]

    # Initialize API
    api = WasteCollectionAPI()

    # Create coordinator with NO automatic updates
    async def async_update_data():
        """Fetch data from API."""
        try:
            return await hass.async_add_executor_job(
                api.update,
                number,
                street_id,
                town_id,
                street_name,
                period_id,
                None,  # Get all types for individual sensors
            )
        except Exception as err:
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