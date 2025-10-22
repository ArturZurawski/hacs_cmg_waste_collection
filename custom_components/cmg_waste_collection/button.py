"""Button platform for Waste Collection."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_TOWN_NAME, CONF_STREET_NAME, CONF_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_device_info(config_entry: ConfigEntry) -> DeviceInfo:
    """Get device info for button entity."""
    return DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name="Waste Collection",
        manufacturer="EcoHarmonogram.pl",
        model=f"{config_entry.data.get(CONF_TOWN_NAME, 'Unknown')} - {config_entry.data.get(CONF_STREET_NAME, '')} {config_entry.data.get(CONF_NUMBER, '')}",
        sw_version="3.0",
        configuration_url="https://ecoharmonogram.pl",
        entry_type="service",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up waste collection button from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    async_add_entities([WasteCollectionRefreshButton(coordinator, config_entry)])


class WasteCollectionRefreshButton(CoordinatorEntity, ButtonEntity):
    """Button to manually refresh waste collection schedule."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = "Refresh schedule"
        self._attr_unique_id = f"{config_entry.entry_id}_refresh_button"
        self._attr_icon = "mdi:refresh"
        self._attr_has_entity_name = True
        self._attr_device_info = get_device_info(config_entry)

    async def async_press(self) -> None:
        """Handle the button press - trigger coordinator refresh."""
        _LOGGER.info("Manual refresh triggered for waste collection schedule")
        await self.coordinator.async_request_refresh()