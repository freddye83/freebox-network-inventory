"""Freebox Network Inventory — HACS integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_APP_TOKEN,
    CONF_SCAN_INTERVAL,
    DATA_API,
    DATA_COORDINATOR,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import FreeboxNetworkCoordinator
from .freebox_api import FreeboxApi, FreeboxApiError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SELECT, Platform.SENSOR, Platform.TEXT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Freebox Network Inventory from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    app_token = entry.data[CONF_APP_TOKEN]
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    api = FreeboxApi(host, port)
    api.set_app_token(app_token)

    try:
        await api.get_api_version()
        await api.open_session()
    except FreeboxApiError as err:
        await api.close()
        raise ConfigEntryNotReady(f"Cannot connect to Freebox: {err}") from err

    coordinator = FreeboxNetworkCoordinator(hass, api, scan_interval)
    await coordinator.async_load_known_devices()

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_API: api,
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update (e.g. scan interval change)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        api: FreeboxApi = data[DATA_API]
        try:
            await api.close_session()
        except Exception:  # noqa: BLE001
            pass
        await api.close()

    return unload_ok
