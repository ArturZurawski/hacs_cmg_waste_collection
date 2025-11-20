"""Sensor platform for Waste Collection."""
from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    ATTR_ALL_DATES,
    ATTR_COLOR,
    ATTR_COMMUNITY_ID,
    ATTR_COUNT,
    ATTR_DAYS_UNTIL,
    ATTR_IS_TODAY,
    ATTR_IS_TOMORROW,
    ATTR_NEXT_DATE,
    ATTR_NEXT_TYPE,
    ATTR_PERIOD_ID,
    ATTR_STREET_ID,
    ATTR_TOWN_ID,
    ATTR_UPCOMING_DATES,
    ATTR_WASTE_TYPE_ID,
    ATTR_WASTE_TYPES,
    CONF_COMMUNITY_ID,
    CONF_NUMBER,
    CONF_PERIOD_CHANGE_DATE,
    CONF_PERIOD_ID,
    CONF_SELECTED_WASTE_TYPES,
    CONF_STREET_ID,
    CONF_STREET_NAME,
    CONF_TOWN_ID,
    CONF_TOWN_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def capitalize_waste_name(name: str) -> str:
    """Capitalize waste type name properly - first letter uppercase, rest lowercase."""
    if not name:
        return name
    # Skip if already has multiple capital letters (like METALE I TWORZYWA)
    if sum(1 for c in name if c.isupper()) > 1:
        return name.title()
    return name[0].upper() + name[1:].lower() if len(name) > 1 else name.upper()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up waste collection sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    await coordinator.async_config_entry_first_refresh()

    entities = []

    if not coordinator.data:
        _LOGGER.warning("No data available from coordinator")
        return

    schedule, descriptions = coordinator.data

    # Clear sensor list (in case of reload)
    hass.data[DOMAIN][config_entry.entry_id]["sensor_list"] = []

    # Create sensor for each waste type
    for waste_type, desc in descriptions.items():
        # Use slugify to match HA's entity_id normalization
        waste_slug = slugify(waste_type)
        entity_id = f"sensor.waste_collection_{waste_slug}"

        # Add to sensor list
        hass.data[DOMAIN][config_entry.entry_id]["sensor_list"].append(entity_id)

        entities.append(
            WasteCollectionSensor(coordinator, config_entry, waste_type, desc)
        )
        _LOGGER.debug("Created sensor '%s' with entity_id: %s", waste_type, entity_id)

    # Create sensor that lists all waste sensors (for card)
    entities.append(
        WasteSensorsListSensor(hass, coordinator, config_entry)
    )

    _LOGGER.info("Created %d waste type sensors, list: %s",
                 len(hass.data[DOMAIN][config_entry.entry_id]["sensor_list"]),
                 hass.data[DOMAIN][config_entry.entry_id]["sensor_list"])

    # Create aggregate sensors
    selected_types = config_entry.options.get(
        CONF_SELECTED_WASTE_TYPES,
        config_entry.data.get(CONF_SELECTED_WASTE_TYPES, [])
    )

    if selected_types:
        entities.append(
            TodayCollectionSensor(coordinator, config_entry, selected_types)
        )
        entities.append(
            TomorrowCollectionSensor(coordinator, config_entry, selected_types)
        )
        entities.append(
            NextCollectionSensor(coordinator, config_entry, selected_types)
        )
        _LOGGER.info("Created aggregate sensors with %d selected waste types", len(selected_types))
    else:
        _LOGGER.warning("NOT creating aggregate sensors - no waste types selected. Please configure waste types in integration options.")

    # Create info sensors
    change_date = config_entry.data.get(CONF_PERIOD_CHANGE_DATE)
    if change_date:
        entities.append(
            ScheduleChangeDateSensor(config_entry, change_date)
        )

    entities.append(
        LastUpdateSensor(coordinator, config_entry)
    )

    entities.append(
        ConfigurationStatusSensor(config_entry)
    )

    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Created %d waste collection sensors", len(entities))
    else:
        _LOGGER.warning("No waste types found in schedule")


def get_device_info(config_entry: ConfigEntry) -> DeviceInfo:
    """Get device info for all entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name="Waste Collection",
        manufacturer="EcoHarmonogram.pl",
        model=f"{config_entry.data.get(CONF_TOWN_NAME, 'Unknown')} - {config_entry.data.get(CONF_STREET_NAME, '')} {config_entry.data.get(CONF_NUMBER, '')}",
        sw_version="3.0",
        configuration_url="https://ecoharmonogram.pl",
        entry_type="service",
    )


class WasteCollectionSensor(CoordinatorEntity, SensorEntity):
    """Sensor for specific waste type."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        waste_type: str,
        description: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._waste_type = waste_type
        self._description = description
        self._config_entry = config_entry
        self._attr_name = capitalize_waste_name(waste_type)
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{waste_type.lower().replace(' ', '_')}"
        )
        self._attr_icon = self._get_icon(waste_type)
        self._attr_has_entity_name = True
        self._attr_device_info = get_device_info(config_entry)

    def _get_icon(self, waste_type: str) -> str:
        """Get icon based on waste type."""
        waste_lower = waste_type.lower()

        if "bio" in waste_lower:
            return "mdi:leaf"
        elif "odpady" in waste_lower or "zielone" in waste_lower:
            return "mdi:grass"
        elif "papier" in waste_lower:
            return "mdi:newspaper"
        elif "szkło" in waste_lower:
            return "mdi:bottle-wine"
        elif "metale" in waste_lower or "tworzywa" in waste_lower:
            return "mdi:recycle"
        elif "resztkowe" in waste_lower or "zmieszane" in waste_lower:
            return "mdi:trash-can"
        elif "gabaryty" in waste_lower:
            return "mdi:truck"
        elif "płatności" in waste_lower or "terminy" in waste_lower:
            return "mdi:cash"
        else:
            return "mdi:delete"

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        next_date = self._get_next_collection()
        if next_date:
            return next_date.strftime("%Y-%m-%d")
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        next_date = self._get_next_collection()

        base_attrs = {
            ATTR_WASTE_TYPE_ID: self._description.get('id'),
            ATTR_COLOR: self._description.get('color'),
            'icon': self._attr_icon,
        }

        if not next_date:
            return {
                **base_attrs,
                ATTR_NEXT_DATE: None,
                ATTR_DAYS_UNTIL: None,
                ATTR_IS_TODAY: False,
                ATTR_IS_TOMORROW: False,
                ATTR_UPCOMING_DATES: [],
                ATTR_ALL_DATES: [],
            }

        today = dt_util.now().date()
        days_until = (next_date.date() - today).days

        all_dates = self._get_all_dates()
        upcoming = [
            d.strftime("%Y-%m-%d")
            for d in all_dates
            if d.date() >= today
        ][:3]

        return {
            **base_attrs,
            ATTR_NEXT_DATE: next_date.strftime("%Y-%m-%d"),
            ATTR_DAYS_UNTIL: days_until,
            ATTR_IS_TODAY: days_until == 0,
            ATTR_IS_TOMORROW: days_until == 1,
            ATTR_UPCOMING_DATES: upcoming,
            ATTR_ALL_DATES: [d.strftime("%Y-%m-%d") for d in all_dates],
        }

    def _get_next_collection(self) -> Optional[datetime]:
        """Get next collection date for this waste type."""
        if not self.coordinator.data:
            return None

        schedule, _ = self.coordinator.data
        dates = schedule.get(self._waste_type, [])

        if not dates:
            return None

        today = dt_util.now().date()
        future_dates = [d for d in dates if d.date() >= today]

        if future_dates:
            return future_dates[0]

        return None

    def _get_all_dates(self) -> List[datetime]:
        """Get all collection dates for this waste type."""
        if not self.coordinator.data:
            return []

        schedule, _ = self.coordinator.data
        dates = schedule.get(self._waste_type, [])
        return dates

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Keep showing last known values even if update fails
        return self.coordinator.data is not None


class TodayCollectionSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing if any selected waste type is collected today."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        selected_type_ids: List[str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        # Don't store selected_type_ids - read dynamically from config_entry
        self._attr_name = "Today collection"
        self._attr_unique_id = f"{config_entry.entry_id}_today_collection"
        self._attr_icon = "mdi:calendar-today"
        self._attr_has_entity_name = True
        self._attr_device_info = get_device_info(config_entry)

    @property
    def _selected_type_ids(self) -> List[str]:
        """Get current selected type IDs from config entry."""
        return self._config_entry.options.get(
            CONF_SELECTED_WASTE_TYPES,
            self._config_entry.data.get(CONF_SELECTED_WASTE_TYPES, [])
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        today_types = self._get_today_types()
        return "Yes" if today_types else "No"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        today_types = self._get_today_types()

        # Get all monitored waste type names
        monitored_types = []
        if self.coordinator.data:
            _, descriptions = self.coordinator.data
            for waste_type, desc in descriptions.items():
                if desc.get('id') in self._selected_type_ids:
                    monitored_types.append(capitalize_waste_name(waste_type))

        return {
            ATTR_WASTE_TYPES: [capitalize_waste_name(t) for t in today_types],
            ATTR_COUNT: len(today_types),
            "monitored_types": monitored_types,
        }

    def _get_today_types(self) -> List[str]:
        """Get list of waste types collected today from selected."""
        if not self.coordinator.data:
            return []

        schedule, descriptions = self.coordinator.data
        today = dt_util.now().date()
        today_types = []

        for waste_type, dates in schedule.items():
            desc = descriptions.get(waste_type, {})
            if desc.get('id') not in self._selected_type_ids:
                continue

            if any(d.date() == today for d in dates):
                today_types.append(waste_type)

        return today_types

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Keep showing last known values even if update fails
        return self.coordinator.data is not None


class TomorrowCollectionSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing if any selected waste type is collected tomorrow."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        selected_type_ids: List[str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        # Don't store selected_type_ids - read dynamically from config_entry
        self._attr_name = "Tomorrow collection"
        self._attr_unique_id = f"{config_entry.entry_id}_tomorrow_collection"
        self._attr_icon = "mdi:calendar"
        self._attr_has_entity_name = True
        self._attr_device_info = get_device_info(config_entry)

    @property
    def _selected_type_ids(self) -> List[str]:
        """Get current selected type IDs from config entry."""
        return self._config_entry.options.get(
            CONF_SELECTED_WASTE_TYPES,
            self._config_entry.data.get(CONF_SELECTED_WASTE_TYPES, [])
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        tomorrow_types = self._get_tomorrow_types()
        return "Yes" if tomorrow_types else "No"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        tomorrow_types = self._get_tomorrow_types()

        # Get all monitored waste type names
        monitored_types = []
        if self.coordinator.data:
            _, descriptions = self.coordinator.data
            for waste_type, desc in descriptions.items():
                if desc.get('id') in self._selected_type_ids:
                    monitored_types.append(capitalize_waste_name(waste_type))

        return {
            ATTR_WASTE_TYPES: [capitalize_waste_name(t) for t in tomorrow_types],
            ATTR_COUNT: len(tomorrow_types),
            "monitored_types": monitored_types,
        }

    def _get_tomorrow_types(self) -> List[str]:
        """Get list of waste types collected tomorrow from selected."""
        if not self.coordinator.data:
            return []

        schedule, descriptions = self.coordinator.data
        today = dt_util.now().date()
        tomorrow = today + timedelta(days=1)
        tomorrow_types = []

        for waste_type, dates in schedule.items():
            desc = descriptions.get(waste_type, {})
            if desc.get('id') not in self._selected_type_ids:
                continue

            if any(d.date() == tomorrow for d in dates):
                tomorrow_types.append(waste_type)

        return tomorrow_types

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Keep showing last known values even if update fails
        return self.coordinator.data is not None


class NextCollectionSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing next collection from selected types."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        selected_type_ids: List[str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        # Don't store selected_type_ids - read dynamically from config_entry
        self._attr_name = "Next collection"
        self._attr_unique_id = f"{config_entry.entry_id}_next_collection"
        self._attr_icon = "mdi:calendar-multiselect"
        self._attr_has_entity_name = True
        self._attr_device_info = get_device_info(config_entry)

    @property
    def _selected_type_ids(self) -> List[str]:
        """Get current selected type IDs from config entry."""
        return self._config_entry.options.get(
            CONF_SELECTED_WASTE_TYPES,
            self._config_entry.data.get(CONF_SELECTED_WASTE_TYPES, [])
        )

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor (next date)."""
        next_info = self._get_next_collection()
        if next_info:
            return next_info['date'].strftime("%Y-%m-%d")
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        next_info = self._get_next_collection()

        # Get all monitored waste type names
        monitored_types = []
        if self.coordinator.data:
            _, descriptions = self.coordinator.data
            for waste_type, desc in descriptions.items():
                if desc.get('id') in self._selected_type_ids:
                    monitored_types.append(capitalize_waste_name(waste_type))

        if not next_info:
            return {
                ATTR_NEXT_TYPE: None,
                ATTR_WASTE_TYPES: [],
                ATTR_DAYS_UNTIL: None,
                ATTR_IS_TODAY: False,
                ATTR_IS_TOMORROW: False,
                "monitored_types": monitored_types,
            }

        today = dt_util.now().date()
        days_until = (next_info['date'].date() - today).days

        return {
            ATTR_NEXT_TYPE: capitalize_waste_name(next_info['types'][0]) if next_info['types'] else None,
            ATTR_WASTE_TYPES: [capitalize_waste_name(t) for t in next_info['types']],
            ATTR_DAYS_UNTIL: days_until,
            ATTR_IS_TODAY: days_until == 0,
            ATTR_IS_TOMORROW: days_until == 1,
            "monitored_types": monitored_types,
        }

    def _get_next_collection(self) -> Optional[Dict[str, Any]]:
        """Get next collection info."""
        if not self.coordinator.data:
            return None

        schedule, descriptions = self.coordinator.data
        today = dt_util.now().date()
        selected_ids = self._selected_type_ids

        future_collections = []

        for waste_type, dates in schedule.items():
            desc = descriptions.get(waste_type, {})
            waste_id = desc.get('id')
            if waste_id not in selected_ids:
                continue

            future_dates = [d for d in dates if d.date() >= today]
            if future_dates:
                future_collections.append({
                    'type': waste_type,
                    'date': future_dates[0]
                })

        if not future_collections:
            _LOGGER.warning("No future collections found for selected waste types")
            return None

        future_collections.sort(key=lambda x: x['date'])
        next_date = future_collections[0]['date']

        types_on_date = [
            c['type'] for c in future_collections
            if c['date'].date() == next_date.date()
        ]

        return {
            'date': next_date,
            'types': types_on_date
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Keep showing last known values even if update fails
        return self.coordinator.data is not None


class ScheduleChangeDateSensor(SensorEntity):
    """Sensor showing when schedule was last changed."""

    def __init__(self, config_entry: ConfigEntry, change_date: str) -> None:
        """Initialize the sensor."""
        self._config_entry = config_entry
        self._change_date = change_date
        self._attr_name = "Schedule last change"
        self._attr_unique_id = f"{config_entry.entry_id}_schedule_change_date"
        self._attr_icon = "mdi:calendar-edit"
        self._attr_has_entity_name = True
        self._attr_device_info = get_device_info(config_entry)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self._change_date

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        return {
            "source": "schedule_period_api",
        }


class WasteSensorsListSensor(CoordinatorEntity, SensorEntity):
    """Sensor listing all waste collection sensor entity IDs."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._hass = hass
        self._config_entry = config_entry
        self._attr_name = "Waste sensors"
        self._attr_unique_id = f"{config_entry.entry_id}_waste_sensors_list"
        self._attr_icon = "mdi:format-list-bulleted"
        self._attr_has_entity_name = True
        self._attr_device_info = get_device_info(config_entry)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int:
        """Return the count of sensors."""
        sensor_list = self._hass.data[DOMAIN][self._config_entry.entry_id].get("sensor_list", [])
        return len(sensor_list)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the list of sensor entity IDs."""
        sensor_list = self._hass.data[DOMAIN][self._config_entry.entry_id].get("sensor_list", [])
        return {
            "entity_ids": sensor_list,
        }


class LastUpdateSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing when data was last fetched."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = "Last update"
        self._attr_unique_id = f"{config_entry.entry_id}_last_update"
        self._attr_icon = "mdi:update"
        self._attr_has_entity_name = True
        self._attr_device_info = get_device_info(config_entry)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> Optional[datetime]:
        """Return the state of the sensor."""
        # coordinator.last_update_success_time might not exist or be bool
        if hasattr(self.coordinator, 'last_update_success_time'):
            last_update = self.coordinator.last_update_success_time
            if isinstance(last_update, datetime):
                return last_update

        # Fallback: if we have data, return current time
        if self.coordinator.data:
            return dt_util.now()

        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        return {
            ATTR_COMMUNITY_ID: self._config_entry.data.get(CONF_COMMUNITY_ID),
            ATTR_TOWN_ID: self._config_entry.data.get(CONF_TOWN_ID),
            ATTR_PERIOD_ID: self._config_entry.data.get(CONF_PERIOD_ID),
            ATTR_STREET_ID: self._config_entry.data.get(CONF_STREET_ID),
            "street_name": self._config_entry.data.get(CONF_STREET_NAME),
            "number": self._config_entry.data.get(CONF_NUMBER),
        }


class ConfigurationStatusSensor(SensorEntity):
    """Sensor showing configuration status of waste types selection."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._config_entry = config_entry
        self._attr_name = "Configuration status"
        self._attr_unique_id = f"{config_entry.entry_id}_configuration_status"
        self._attr_icon = "mdi:cog"
        self._attr_has_entity_name = True
        self._attr_device_info = get_device_info(config_entry)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        selected_types = self._config_entry.options.get(
            CONF_SELECTED_WASTE_TYPES,
            self._config_entry.data.get(CONF_SELECTED_WASTE_TYPES, [])
        )

        if not selected_types:
            return "not_selected"
        return "configured"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        selected_types = self._config_entry.options.get(
            CONF_SELECTED_WASTE_TYPES,
            self._config_entry.data.get(CONF_SELECTED_WASTE_TYPES, [])
        )

        return {
            "selected_count": len(selected_types),
            "selected_type_ids": selected_types,
        }