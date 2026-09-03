"""Config flow for Uponor R-167."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import UponorApiClient, UponorApiError
from .const import (
    CONF_MAX_CHANNELS,
    CONF_SCAN_INTERVAL,
    DEFAULT_MAX_CHANNELS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Optional(CONF_MAX_CHANNELS, default=DEFAULT_MAX_CHANNELS): int,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


class UponorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Simple single-step form: only the IP address is needed."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return UponorOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = UponorApiClient(
                host=user_input["host"],
                session=session,
                max_channels=user_input[CONF_MAX_CHANNELS],
            )
            try:
                rooms = await client.discover_and_read()
            except UponorApiError:
                errors["base"] = "cannot_connect"
            else:
                if not rooms:
                    errors["base"] = "no_rooms_found"
                else:
                    await self.async_set_unique_id(user_input["host"])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Uponor",
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )


class UponorOptionsFlow(config_entries.OptionsFlow):
    """Lets the user change max_channels/scan_interval after setup."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_max = self.config_entry.options.get(
            CONF_MAX_CHANNELS,
            self.config_entry.data.get(CONF_MAX_CHANNELS, DEFAULT_MAX_CHANNELS),
        )
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_MAX_CHANNELS, default=current_max): int,
                vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
