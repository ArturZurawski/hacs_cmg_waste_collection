"""Constants for the Waste Collection integration."""

DOMAIN = "cmg_waste_collection"

# API
BASE_URL = "https://pluginecoapi.ecoharmonogram.pl/v1"

# Configuration keys
CONF_COMMUNITY_ID = "community_id"
CONF_TOWN_ID = "town_id"
CONF_TOWN_NAME = "town_name"
CONF_PERIOD_ID = "period_id"
CONF_PERIOD_START = "period_start"
CONF_PERIOD_END = "period_end"
CONF_PERIOD_CHANGE_DATE = "period_change_date"
CONF_STREET_NAME = "street_name"
CONF_STREET_CHOOSED_IDS = "street_choosed_ids"
CONF_NUMBER = "number"
CONF_STREET_ID = "street_id"
CONF_GROUP_NAME = "group_name"
CONF_SELECTED_WASTE_TYPES = "selected_waste_types"
CONF_EVENT_TIME = "event_time"

# Defaults
DEFAULT_COMMUNITY_ID = "108"
DEFAULT_EVENT_TIME = "6"  # Default to 6:00 AM

# Sensor attributes
ATTR_NEXT_DATE = "next_date"
ATTR_DAYS_UNTIL = "days_until"
ATTR_IS_TODAY = "is_today"
ATTR_IS_TOMORROW = "is_tomorrow"
ATTR_UPCOMING_DATES = "upcoming_dates"
ATTR_ALL_DATES = "all_dates"
ATTR_WASTE_TYPE_ID = "waste_type_id"
ATTR_COLOR = "color"
ATTR_DESCRIPTION = "description"
ATTR_WASTE_TYPES = "waste_types"
ATTR_COUNT = "count"
ATTR_NEXT_TYPE = "next_waste_type"

# Device info attributes
ATTR_COMMUNITY_ID = "community_id"
ATTR_TOWN_ID = "town_id"
ATTR_PERIOD_ID = "period_id"
ATTR_STREET_ID = "street_id"