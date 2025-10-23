"""Calendar platform for Waste Collection."""
from datetime import date, datetime, timedelta
import logging
from typing import Optional

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EVENT_TIME,
    CONF_NUMBER,
    CONF_STREET_NAME,
    CONF_TOWN_NAME,
    DEFAULT_EVENT_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def capitalize_waste_name(name: str) -> str:
    """Capitalize waste type name properly."""
    if not name:
        return name
    if sum(1 for c in name if c.isupper()) > 1:
        return name.title()
    return name[0].upper() + name[1:].lower() if len(name) > 1 else name.upper()


def get_color_emoji(color: str) -> str:
    """Get colored emoji square based on hex color."""
    color = color.lower()

    # Map CMG colors to emoji squares
    color_map = {
        "#ae6f46": "🟫",  # BIO - brown
        "#9d9d9c": "⬛",  # RESZTKOWE - gray
        "#303030": "⬛",  # RESZTKOWE alt - dark gray
        "#009fe3": "🟦",  # PAPIER - blue
        "#fed000": "🟨",  # METALE - yellow
        "#ffff00": "🟨",  # METALE alt - yellow
        "#3aaa35": "🟩",  # SZKŁO - green
        "#d1d1d1": "⬜",  # WIELKOGABARYTY - light gray
        "#c0c0c0": "⬜",  # WIELKOGABARYTY alt - light gray
        "#e30000": "🟥",  # TERMINY PŁATNOŚCI - red
        "#ff0000": "🟥",  # TERMINY PŁATNOŚCI alt - red
    }

    return color_map.get(color, "🔲")  # Default: gray square


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up waste collection calendar from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.data:
        _LOGGER.warning("No data available from coordinator for calendar")
        return

    # Create single calendar entity for all waste types
    async_add_entities([WasteCollectionCalendar(coordinator, config_entry)])


def get_device_info(config_entry: ConfigEntry) -> DeviceInfo:
    """Get device info for calendar entity."""
    return DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name="Waste Collection",
        manufacturer="EcoHarmonogram.pl",
        model=f"{config_entry.data.get(CONF_TOWN_NAME, 'Unknown')} - {config_entry.data.get(CONF_STREET_NAME, '')} {config_entry.data.get(CONF_NUMBER, '')}",
        sw_version="3.0",
        configuration_url="https://ecoharmonogram.pl",
        entry_type="service",
    )


class WasteCollectionCalendar(CoordinatorEntity, CalendarEntity):
    """Calendar entity showing all waste collection dates."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = "Waste Collection"
        self._attr_unique_id = f"{config_entry.entry_id}_calendar"
        self._attr_has_entity_name = True
        self._attr_device_info = get_device_info(config_entry)
        self._event = None

    def _get_event_time_setting(self) -> str:
        """Get the event time setting from options or config data or default."""
        # First check options (can be changed after initial config)
        # Then check config data (set during initial config)
        # Finally use default
        return self._config_entry.options.get(
            CONF_EVENT_TIME,
            self._config_entry.data.get(CONF_EVENT_TIME, DEFAULT_EVENT_TIME)
        )

    @property
    def event(self) -> Optional[CalendarEvent]:
        """Return the next upcoming event."""
        if not self.coordinator.data:
            return None

        schedule, descriptions = self.coordinator.data
        now = dt_util.now()
        today = now.date()

        # Find next event
        next_events = []
        for waste_type, dates in schedule.items():
            desc = descriptions.get(waste_type, {})
            for collection_date in dates:
                if collection_date.date() >= today:
                    next_events.append({
                        'date': collection_date,
                        'waste_type': waste_type,
                        'color': desc.get('color', '#808080'),
                    })

        if not next_events:
            return None

        # Sort by date and get the first one
        next_events.sort(key=lambda x: x['date'])
        next_event = next_events[0]

        # Get colored emoji
        color_emoji = get_color_emoji(next_event['color'])
        waste_name = capitalize_waste_name(next_event['waste_type'])

        # Simple description: emoji + name
        summary = f"{color_emoji} {waste_name}"

        # Get event time setting
        event_time = self._get_event_time_setting()

        if event_time == "all_day":
            # All-day event
            event_date = next_event['date'].date()
            return CalendarEvent(
                start=event_date,
                end=event_date + timedelta(days=1),
                summary=summary,
                description=summary,
            )
        else:
            # Event at specific hour
            hour = int(event_time)
            event_datetime = datetime.combine(
                next_event['date'].date(),
                datetime.min.time().replace(hour=hour)
            )
            event_datetime = dt_util.as_local(event_datetime)
            
            return CalendarEvent(
                start=event_datetime,
                end=event_datetime + timedelta(hours=1),
                summary=summary,
                description=summary,
            )

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        if not self.coordinator.data:
            return []

        schedule, descriptions = self.coordinator.data
        events = []

        # Get event time setting
        event_time = self._get_event_time_setting()

        for waste_type, dates in schedule.items():
            desc = descriptions.get(waste_type, {})
            color = desc.get('color', '#808080')

            # Get colored emoji
            color_emoji = get_color_emoji(color)
            waste_name = capitalize_waste_name(waste_type)

            # Simple description: emoji + name
            summary = f"{color_emoji} {waste_name}"

            for collection_date in dates:
                # Check if date is within requested range
                if start_date.date() <= collection_date.date() <= end_date.date():
                    
                    if event_time == "all_day":
                        # All-day event
                        event_date = collection_date.date()
                        events.append(
                            CalendarEvent(
                                start=event_date,
                                end=event_date + timedelta(days=1),
                                summary=summary,
                                description=summary,
                            )
                        )
                    else:
                        # Event at specific hour
                        hour = int(event_time)
                        event_datetime = datetime.combine(
                            collection_date.date(),
                            datetime.min.time().replace(hour=hour)
                        )
                        event_datetime = dt_util.as_local(event_datetime)
                        
                        events.append(
                            CalendarEvent(
                                start=event_datetime,
                                end=event_datetime + timedelta(hours=1),
                                summary=summary,
                                description=summary,
                            )
                        )

        # Sort events by start date
        events.sort(key=lambda x: x.start)
        return events

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None
