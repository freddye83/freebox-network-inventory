"""Text entity — nom modifiable d'un équipement réseau Freebox."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_ALIAS, ATTR_MAC, DATA_API, DATA_COORDINATOR, DOMAIN
from .coordinator import FreeboxNetworkCoordinator
from .entity_base import FreeboxDeviceEntity
from .freebox_api import FreeboxApi, FreeboxApiError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up text entities."""
    coordinator: FreeboxNetworkCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    api: FreeboxApi = hass.data[DOMAIN][entry.entry_id][DATA_API]
    known: set[str] = set()

    def _add() -> None:
        if not coordinator.data:
            return
        new = [
            FreeboxDeviceNameText(coordinator, entry, mac, api)
            for mac in coordinator.data if mac not in known
        ]
        for e in new:
            known.add(e._mac)
        if new:
            async_add_entities(new)

    _add()
    entry.async_on_unload(coordinator.async_add_listener(_add))


class FreeboxDeviceNameText(FreeboxDeviceEntity, TextEntity):
    """Champ texte pour renommer un équipement dans Freebox OS."""

    _attr_mode = TextMode.TEXT
    _attr_native_min = 1
    _attr_native_max = 64
    _attr_translation_key = "device_name"
    _attr_icon = "mdi:rename"

    def __init__(
        self,
        coordinator: FreeboxNetworkCoordinator,
        entry: ConfigEntry,
        mac: str,
        api: FreeboxApi,
    ) -> None:
        super().__init__(coordinator, entry, mac)
        self._api = api
        d = coordinator.data.get(mac, {})
        slug = d.get("slug", mac.replace(":", "_").lower())
        self._attr_unique_id = f"{DOMAIN}_{mac}_name"
        self.entity_id = f"text.{DOMAIN}_{slug}_nom"

    @property
    def name(self) -> str:
        return "Nom"

    @property
    def native_value(self) -> str | None:
        return self._device_data.get(ATTR_ALIAS) or self._device_data.get("friendly_name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose la MAC pour que la carte puisse faire le lien."""
        return {ATTR_MAC: self._mac}

    async def async_set_value(self, value: str) -> None:
        """Envoie le nouveau nom à la Freebox."""
        raw = self._device_data.get("raw", {})
        host_id = raw.get("id")
        if not host_id:
            _LOGGER.error("Cannot rename device %s: no host id in raw data", self._mac)
            return
        try:
            _LOGGER.debug("PUT /lan/browser/pub/%s → primary_name=%s", host_id, value)
            await self._api.update_lan_host(host_id, {
                "primary_name": value,
                "primary_name_manual": True,
            })
            _LOGGER.info("Renamed %s → '%s' (id=%s)", self._mac, value, host_id)
            await self.coordinator.async_request_refresh()
        except FreeboxApiError as err:
            _LOGGER.error("Failed to rename device %s: %s", self._mac, err)
