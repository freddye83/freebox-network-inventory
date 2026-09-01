"""Binary sensor (online/offline) for Freebox Network Inventory."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_REACHABLE, DATA_COORDINATOR, DOMAIN
from .coordinator import FreeboxNetworkCoordinator
from .entity_base import FreeboxDeviceEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FreeboxNetworkCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    known: set[str] = set()

    def _add() -> None:
        if not coordinator.data:
            return
        new = [FreeboxOnlineBinarySensor(coordinator, entry, mac)
               for mac in coordinator.data if mac not in known]
        for e in new:
            known.add(e._mac)
        if new:
            async_add_entities(new)

    _add()
    entry.async_on_unload(coordinator.async_add_listener(_add))


class FreeboxOnlineBinarySensor(FreeboxDeviceEntity, BinarySensorEntity):
    """True when device is reachable on the network."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "online"

    def __init__(self, coordinator, entry, mac):
        super().__init__(coordinator, entry, mac)
        # entity_id : binary_sensor.freebox_network_inventory_<slug>_en_ligne
        slug = coordinator.data.get(mac, {}).get("slug", mac.replace(":", "_").lower())
        self._attr_unique_id = f"{DOMAIN}_{mac}_online"
        self.entity_id = f"binary_sensor.{DOMAIN}_{slug}_en_ligne"

    @property
    def name(self) -> str:
        return "En ligne"

    @property
    def is_on(self) -> bool | None:
        return self._device_data.get(ATTR_REACHABLE)
