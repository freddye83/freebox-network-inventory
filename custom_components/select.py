"""Select entity — type d'équipement modifiable dans Freebox OS."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_HOST_TYPE, ATTR_MAC, DATA_API, DATA_COORDINATOR, DOMAIN, HOST_TYPE_LABELS
from .coordinator import FreeboxNetworkCoordinator
from .entity_base import FreeboxDeviceEntity
from .freebox_api import FreeboxApi, FreeboxApiError

_LOGGER = logging.getLogger(__name__)

# Libellé FR → clé API Freebox
LABEL_TO_KEY: dict[str, str] = {v: k for k, v in HOST_TYPE_LABELS.items()}
OPTIONS: list[str] = sorted(HOST_TYPE_LABELS.values())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator: FreeboxNetworkCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    api: FreeboxApi = hass.data[DOMAIN][entry.entry_id][DATA_API]
    known: set[str] = set()

    def _add() -> None:
        if not coordinator.data:
            return
        new = [
            FreeboxDeviceTypeSelect(coordinator, entry, mac, api)
            for mac in coordinator.data if mac not in known
        ]
        for e in new:
            known.add(e._mac)
        if new:
            async_add_entities(new)

    _add()
    entry.async_on_unload(coordinator.async_add_listener(_add))


class FreeboxDeviceTypeSelect(FreeboxDeviceEntity, SelectEntity):
    """Liste déroulante pour changer le type d'un équipement dans Freebox OS."""

    _attr_translation_key = "device_type"
    _attr_icon = "mdi:devices"

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
        self._attr_unique_id = f"{DOMAIN}_{mac}_type"
        self.entity_id = f"select.{DOMAIN}_{slug}_type"
        self._attr_options = OPTIONS

    @property
    def name(self) -> str:
        return "Type"

    @property
    def current_option(self) -> str | None:
        raw_type = self._device_data.get(ATTR_HOST_TYPE, "")
        return HOST_TYPE_LABELS.get(raw_type)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose la MAC pour que la carte puisse faire le lien."""
        return {ATTR_MAC: self._mac}

    async def async_select_option(self, option: str) -> None:
        """Envoie le nouveau type à la Freebox."""
        api_key = LABEL_TO_KEY.get(option)
        if not api_key:
            _LOGGER.error("Unknown host type label: %s", option)
            return
        raw = self._device_data.get("raw", {})
        host_id = raw.get("id")
        if not host_id:
            _LOGGER.error("Cannot update type for %s: no host id in raw data", self._mac)
            return
        try:
            _LOGGER.debug("PUT /lan/browser/pub/%s → host_type=%s", host_id, api_key)
            await self._api.update_lan_host(host_id, {"host_type": api_key})
            _LOGGER.info("Updated type %s → %s (%s)", self._mac, option, api_key)
            await self.coordinator.async_request_refresh()
        except FreeboxApiError as err:
            _LOGGER.error("Failed to update type for %s: %s", self._mac, err)
