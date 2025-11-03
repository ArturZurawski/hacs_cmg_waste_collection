"""Calendar platform for Waste Collection."""
from datetime import date, datetime, timedelta
import logging
import unicodedata
from typing import Optional

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
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


def normalize_polish_text(text: str) -> str:
    """Normalize Polish text - remove diacritics and convert to ASCII.

    Handles Polish characters: ą, ć, ę, ł, ń, ó, ś, ź, ż
    """
    if not text:
        return text

    # First handle ł/Ł manually as it's not a standard diacritic
    text = text.replace('ł', 'l').replace('Ł', 'L')

    # Use Unicode normalization to remove other diacritics
    # NFD = Normalization Form Decomposed (separates base char from diacritic)
    nfd = unicodedata.normalize('NFD', text)

    # Filter out combining diacritical marks (category 'Mn')
    return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')


def get_color_emoji_from_hex(color: str) -> str:
    """Map any HEX color to closest colored emoji square based on RGB analysis."""
    if not color or not color.startswith('#'):
        return "🔲"

    try:
        color = color.lstrip('#')
        if len(color) != 6:
            return "🔲"

        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)

        # Find max/min components
        max_val = max(r, g, b)
        min_val = min(r, g, b)

        # Black
        if max_val < 50:
            return "⬛"

        # White
        if min_val > 200:
            return "⬜"

        # Gray (low saturation)
        if max_val - min_val < 40:
            if max_val < 180:
                return "⬛"
            else:
                return "⬜"

        # Red
        if r == max_val and r > 180 and r - g > 50 and r - b > 50:
            return "🟥"

        # Yellow (high R and G, low B)
        if r > 200 and g > 150 and b < 100:
            return "🟨"

        # Orange (between red and yellow)
        if r > 200 and g > 100 and g < 180 and b < 100:
            return "🟧"

        # Green
        if g == max_val and g > 100 and g - r > 30 and g - b > 30:
            return "🟩"

        # Blue
        if b == max_val and b > 100 and b - r > 30 and b - g > 30:
            return "🟦"

        # Purple (high R and B)
        if r > 100 and b > 100 and abs(r - b) < 50 and g < max(r, b) - 30:
            return "🟪"

        # Brown (orange-ish but darker)
        if r > 80 and g > 50 and b < 80 and r > g and g > b:
            return "🟫"

        # Default
        return "🔲"

    except (ValueError, IndexError):
        return "🔲"


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
        self._attr_name = "CMG Waste Collection"  # Proper capitalization
        self._attr_unique_id = f"{config_entry.entry_id}_calendar"
        self._attr_has_entity_name = False
        self._attr_device_info = get_device_info(config_entry)
        self._attr_icon = "mdi:trash-can"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
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

    def _get_sensor_color(self, waste_type: str) -> str:
        """Get color from sensor attribute for waste type."""
        # Normalize waste_type for entity_id (remove polish characters, spaces to underscores, lowercase)
        normalized = normalize_polish_text(waste_type.lower()).replace(' ', '_')

        # Entity ID format: sensor.waste_collection_{waste_type}
        entity_id = f"sensor.waste_collection_{normalized}"

        # Try to get sensor state and color attribute
        state = self.hass.states.get(entity_id)
        if state and state.attributes.get('color'):
            return state.attributes['color']

        # Fallback to coordinator descriptions if sensor not found
        if self.coordinator.data:
            _, descriptions = self.coordinator.data
            desc = descriptions.get(waste_type, {})
            return desc.get('color', '#808080')

        return '#808080'

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
            for collection_date in dates:
                if collection_date.date() >= today:
                    next_events.append({
                        'date': collection_date,
                        'waste_type': waste_type,
                        'color': self._get_sensor_color(waste_type),
                    })

        if not next_events:
            return None

        # Sort by date and get the first one
        next_events.sort(key=lambda x: x['date'])
        next_event = next_events[0]

        # Get colored emoji from sensor color attribute
        color_emoji = get_color_emoji_from_hex(next_event['color'])
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
            # Get color from sensor attribute
            color = self._get_sensor_color(waste_type)

            # Get colored emoji from sensor color
            color_emoji = get_color_emoji_from_hex(color)
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