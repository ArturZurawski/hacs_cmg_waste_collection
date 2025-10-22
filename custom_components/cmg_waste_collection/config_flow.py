"""Config flow for Waste Collection integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .api import WasteCollectionAPI
from .const import (
    CONF_COMMUNITY_ID,
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
    CONF_TOWN_NAME,
    DEFAULT_COMMUNITY_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class WasteCollectionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Waste Collection."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.api = WasteCollectionAPI()
        self.data = {}

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step - Community ID."""
        errors = {}

        if user_input is not None:
            self.data[CONF_COMMUNITY_ID] = user_input[CONF_COMMUNITY_ID]
            return await self.async_step_town()

        data_schema = vol.Schema({
            vol.Required(CONF_COMMUNITY_ID, default=DEFAULT_COMMUNITY_ID): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_town(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle town selection."""
        errors = {}

        if user_input is not None:
            town_data = user_input["town"].split("|")
            self.data[CONF_TOWN_ID] = town_data[0]
            self.data[CONF_TOWN_NAME] = town_data[1] if len(town_data) > 1 else town_data[0]
            return await self.async_step_period()

        try:
            towns = await self.hass.async_add_executor_job(
                self.api.get_towns, self.data[CONF_COMMUNITY_ID]
            )

            if not towns:
                errors["base"] = "no_towns_found"
                return await self.async_step_user()

            town_options = {
                f"{town['id']}|{town['name']}": town['name']
                for town in towns
            }

            data_schema = vol.Schema({
                vol.Required("town"): vol.In(town_options),
            })

            return self.async_show_form(
                step_id="town",
                data_schema=data_schema,
                errors=errors,
            )

        except Exception as err:
            _LOGGER.error("Error fetching towns: %s", err)
            errors["base"] = "api_error"
            return await self.async_step_user()

    async def async_step_period(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle schedule period selection."""
        errors = {}

        if user_input is not None:
            period_parts = user_input["period"].split("|")
            self.data[CONF_PERIOD_ID] = period_parts[0]
            self.data[CONF_PERIOD_START] = period_parts[1]
            self.data[CONF_PERIOD_END] = period_parts[2]
            self.data[CONF_PERIOD_CHANGE_DATE] = period_parts[3]
            return await self.async_step_street()

        try:
            periods = await self.hass.async_add_executor_job(
                self.api.get_schedule_periods, self.data[CONF_COMMUNITY_ID]
            )

            if not periods:
                errors["base"] = "no_periods_found"
                return await self.async_step_town()

            period_options = {
                f"{p['id']}|{p['startDate']}|{p['endDate']}|{p['changeDate']}":
                f"{p['startDate']} - {p['endDate']}"
                for p in periods
            }

            data_schema = vol.Schema({
                vol.Required("period"): vol.In(period_options),
            })

            return self.async_show_form(
                step_id="period",
                data_schema=data_schema,
                errors=errors,
            )

        except Exception as err:
            _LOGGER.error("Error fetching periods: %s", err)
            errors["base"] = "api_error"
            return await self.async_step_town()

    async def async_step_street(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle street selection."""
        errors = {}

        if user_input is not None:
            street_parts = user_input["street"].split("|")
            self.data[CONF_STREET_NAME] = street_parts[0]
            self.data[CONF_STREET_CHOOSED_IDS] = street_parts[1]
            return await self.async_step_number()

        try:
            streets = await self.hass.async_add_executor_job(
                self.api.get_streets,
                self.data[CONF_TOWN_ID],
                self.data[CONF_PERIOD_ID]
            )

            if not streets:
                errors["base"] = "no_streets_found"
                return await self.async_step_period()

            street_options = {
                f"{s['name']}|{s['choosedStreetIds']}": s['name']
                for s in streets
            }

            data_schema = vol.Schema({
                vol.Required("street"): vol.In(street_options),
            })

            return self.async_show_form(
                step_id="street",
                data_schema=data_schema,
                errors=errors,
            )

        except Exception as err:
            _LOGGER.error("Error fetching streets: %s", err)
            errors["base"] = "api_error"
            return await self.async_step_period()

    async def async_step_number(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle building number input."""
        errors = {}

        if user_input is not None:
            self.data[CONF_NUMBER] = user_input[CONF_NUMBER]
            return await self.async_step_group()

        data_schema = vol.Schema({
            vol.Required(CONF_NUMBER): str,
        })

        return self.async_show_form(
            step_id="number",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_group(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle building type/group selection."""
        errors = {}

        if user_input is not None:
            group_parts = user_input["group"].split("|")
            self.data[CONF_GROUP_NAME] = group_parts[0]
            self.data[CONF_STREET_ID] = group_parts[1]
            return await self.async_step_waste_types()

        try:
            groups = await self.hass.async_add_executor_job(
                self.api.get_building_groups,
                self.data[CONF_STREET_CHOOSED_IDS],
                self.data[CONF_NUMBER],
                self.data[CONF_TOWN_ID],
                self.data[CONF_STREET_NAME],
                self.data[CONF_PERIOD_ID]
            )

            if not groups:
                errors["base"] = "no_groups_found"
                return await self.async_step_number()

            group_options = {
                f"{g['name']}|{g['choosedStreetIds']}": g['name']
                for g in groups
            }

            data_schema = vol.Schema({
                vol.Required("group"): vol.In(group_options),
            })

            return self.async_show_form(
                step_id="group",
                data_schema=data_schema,
                errors=errors,
            )

        except Exception as err:
            _LOGGER.error("Error fetching groups: %s", err)
            errors["base"] = "api_error"
            return await self.async_step_number()

    async def async_step_waste_types(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle waste type selection."""
        errors = {}

        if user_input is not None:
            # Save selected waste types
            self.data[CONF_SELECTED_WASTE_TYPES] = user_input.get(
                CONF_SELECTED_WASTE_TYPES, []
            )

            # Create entry directly
            await self.async_set_unique_id(
                f"{self.data[CONF_TOWN_ID]}_{self.data[CONF_STREET_ID]}_{self.data[CONF_NUMBER]}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{self.data[CONF_TOWN_NAME]} - {self.data[CONF_STREET_NAME]} {self.data[CONF_NUMBER]}",
                data=self.data,
            )

        try:
            raw_data = await self.hass.async_add_executor_job(
                self.api.get_waste_types,
                self.data[CONF_NUMBER],
                self.data[CONF_STREET_ID],
                self.data[CONF_TOWN_ID],
                self.data[CONF_STREET_NAME],
                self.data[CONF_PERIOD_ID]
            )

            descriptions = raw_data.get('scheduleDescription', [])

            if not descriptions:
                errors["base"] = "no_waste_types_found"
                return await self.async_step_group()

            waste_type_options = {
                desc['id']: desc['name']
                for desc in descriptions
            }

            data_schema = vol.Schema({
                vol.Optional(
                    CONF_SELECTED_WASTE_TYPES,
                    default=list(waste_type_options.keys())
                ): cv.multi_select(waste_type_options),
            })

            return self.async_show_form(
                step_id="waste_types",
                data_schema=data_schema,
                errors=errors,
                description_placeholders={
                    "info": "Select waste types for aggregate sensors"
                }
            )

        except Exception as err:
            _LOGGER.error("Error fetching waste types: %s", err)
            errors["base"] = "api_error"
            return await self.async_step_group()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "WasteCollectionOptionsFlow":
        """Get the options flow for this handler."""
        return WasteCollectionOptionsFlow(config_entry)


class WasteCollectionOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Waste Collection."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.api = WasteCollectionAPI()

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        try:
            raw_data = await self.hass.async_add_executor_job(
                self.api.get_waste_types,
                self.config_entry.data[CONF_NUMBER],
                self.config_entry.data[CONF_STREET_ID],
                self.config_entry.data[CONF_TOWN_ID],
                self.config_entry.data[CONF_STREET_NAME],
                self.config_entry.data[CONF_PERIOD_ID]
            )

            descriptions = raw_data.get('scheduleDescription', [])
            waste_type_options = {
                desc['id']: desc['name']
                for desc in descriptions
            }

            current_selection = self.config_entry.options.get(
                CONF_SELECTED_WASTE_TYPES,
                self.config_entry.data.get(CONF_SELECTED_WASTE_TYPES, list(waste_type_options.keys()))
            )

            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({
                    vol.Optional(
                        CONF_SELECTED_WASTE_TYPES,
                        default=current_selection
                    ): cv.multi_select(waste_type_options),
                }),
                errors=errors,
                description_placeholders={
                    "info": "Select which waste types to include in aggregate sensors"
                }
            )

        except Exception as err:
            _LOGGER.error("Error fetching waste types in options: %s", err)
            errors["base"] = "api_error"
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors=errors,
            )