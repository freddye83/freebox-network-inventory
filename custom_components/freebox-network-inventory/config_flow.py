"""Config flow for Freebox Network Inventory."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_APP_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .freebox_api import FreeboxApi, FreeboxApiError

_LOGGER = logging.getLogger(__name__)

STEP_HOST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

STEP_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=10, max=3600)
        ),
    }
)


class FreeboxNetworkInventoryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Freebox Network Inventory."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._host: str = DEFAULT_HOST
        self._port: int = DEFAULT_PORT
        self._track_id: str = ""
        self._api: FreeboxApi | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: collect host and port."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]

            self._api = FreeboxApi(self._host, self._port)
            try:
                await self._api.get_api_version()
            except FreeboxApiError:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_authorize()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_HOST_SCHEMA,
            errors=errors,
            description_placeholders={"host": DEFAULT_HOST},
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: request authorization on the Freebox LCD screen."""
        errors: dict[str, str] = {}

        if self._api is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            # User clicked confirm — check status
            try:
                status = await self._api.get_authorization_status(self._track_id)
            except FreeboxApiError:
                errors["base"] = "cannot_connect"
            else:
                if status == "granted":
                    app_token = self._api.app_token
                    await self._api.close()
                    return self.async_create_entry(
                        title=f"Freebox ({self._host})",
                        data={
                            CONF_HOST: self._host,
                            CONF_PORT: self._port,
                            CONF_APP_TOKEN: app_token,
                            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        },
                    )
                elif status == "pending":
                    errors["base"] = "authorize_pending"
                elif status == "denied":
                    errors["base"] = "authorize_denied"
                elif status == "timeout":
                    errors["base"] = "authorize_timeout"
                else:
                    errors["base"] = "authorize_unknown"

        if not self._track_id:
            # First time on this step — request authorization
            try:
                _app_token, self._track_id = await self._api.authorize()
            except FreeboxApiError:
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="authorize",
                    errors=errors,
                )

        return self.async_show_form(
            step_id="authorize",
            errors=errors,
            description_placeholders={"host": self._host},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> FreeboxNetworkInventoryOptionsFlow:
        """Return the options flow."""
        return FreeboxNetworkInventoryOptionsFlow(config_entry)


class FreeboxNetworkInventoryOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Freebox Network Inventory."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                        int, vol.Range(min=10, max=3600)
                    ),
                }
            ),
        )
