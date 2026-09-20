"""Binary sensors for Freebox Network Inventory."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_REACHABLE,
    DATA_COORDINATOR,
    DATA_SWITCH_COORDINATOR,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import FreeboxNetworkCoordinator
from .entity_base import FreeboxDeviceEntity
from .switch_coordinator import FreeboxSwitchCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors — appareils LAN + ports switch."""

    # ── Appareils LAN ─────────────────────────────────────────────────────────
    coordinator: FreeboxNetworkCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    known: set[str] = set()

    def _add_device() -> None:
        if not coordinator.data:
            return
        new = [
            FreeboxOnlineBinarySensor(coordinator, entry, mac)
            for mac in coordinator.data if mac not in known
        ]
        for e in new:
            known.add(e._mac)
        if new:
            async_add_entities(new)

    _add_device()
    entry.async_on_unload(coordinator.async_add_listener(_add_device))

    # ── Ports switch ──────────────────────────────────────────────────────────
    switch_coordinator: FreeboxSwitchCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_SWITCH_COORDINATOR
    ]

    if switch_coordinator.data:
        switch_entities = [
            FreeboxSwitchPortLinkSensor(switch_coordinator, entry, port_id)
            for port_id in switch_coordinator.data
        ]
        if switch_entities:
            async_add_entities(switch_entities)


# ── Appareil LAN — en ligne ───────────────────────────────────────────────────

class FreeboxOnlineBinarySensor(FreeboxDeviceEntity, BinarySensorEntity):
    """True quand l'appareil est joignable sur le réseau."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, entry, mac):
        super().__init__(coordinator, entry, mac)
        d = coordinator.data.get(mac, {})
        slug = d.get("slug", mac.replace(":", "_").lower())
        self._attr_unique_id = f"{DOMAIN}_{mac}_online"
        self.entity_id = f"binary_sensor.{DOMAIN}_{slug}_en_ligne"

    @property
    def name(self) -> str:
        return "En ligne"

    @property
    def is_on(self) -> bool | None:
        return self._device_data.get(ATTR_REACHABLE)


# ── Port switch — lien ────────────────────────────────────────────────────────

class FreeboxSwitchPortLinkSensor(
    CoordinatorEntity[FreeboxSwitchCoordinator], BinarySensorEntity
):
    """True quand le port switch est connecté (lien up)."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: FreeboxSwitchCoordinator,
        entry: ConfigEntry,
        port_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._port_id   = port_id
        self._entry     = entry
        self._attr_unique_id = f"{DOMAIN}_switch_port_{port_id}_link"
        self.entity_id = f"binary_sensor.{DOMAIN}_switch_port_{port_id}_lien"

    @property
    def _port_data(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get(self._port_id, {})
        return {}

    @property
    def name(self) -> str:
        return "Lien"

    @property
    def is_on(self) -> bool:
        return self._port_data.get("link") == "up"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._port_data
        mac_list = d.get("mac_list", [])
        return {
            "port_id":   self._port_id,
            "speed":     f"{d.get('speed', '0')} Mbps" if d.get("speed") else None,
            "duplex":    d.get("duplex"),
            "mode":      d.get("mode"),
            "appareils": [m.get("hostname") or m.get("mac") for m in mac_list],
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"switch_port_{self._port_id}")},
            name=f"Switch Freebox — Port {self._port_id}",
            manufacturer=MANUFACTURER,
            model="Switch intégré",
            entry_type=DeviceEntryType.SERVICE,
        )
