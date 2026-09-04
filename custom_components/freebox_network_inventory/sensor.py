"""Sensors for Freebox Network Inventory."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_COORDINATOR, DOMAIN, MANUFACTURER,
    SENSOR_DEVICES_NEW, SENSOR_DEVICES_ONLINE, SENSOR_DEVICES_TOTAL,
)
from .coordinator import FreeboxNetworkCoordinator
from .entity_base import FreeboxDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FreeboxNetworkCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    known: set[str] = set()

    # Capteurs globaux (hub) — une seule fois
    async_add_entities([
        FreeboxGlobalSensor(coordinator, entry, SENSOR_DEVICES_ONLINE,
                            "Appareils en ligne", "mdi:devices",
                            lambda c: c.get_stats()["online"]),
        FreeboxGlobalSensor(coordinator, entry, SENSOR_DEVICES_TOTAL,
                            "Total appareils", "mdi:lan",
                            lambda c: c.get_stats()["total"]),
        FreeboxGlobalSensor(coordinator, entry, SENSOR_DEVICES_NEW,
                            "Nouveaux appareils", "mdi:new-box",
                            lambda c: c.new_device_count),
    ])

    def _add() -> None:
        if not coordinator.data:
            return
        new = [FreeboxDeviceStatusSensor(coordinator, entry, mac)
               for mac in coordinator.data if mac not in known]
        for e in new:
            known.add(e._mac)
        if new:
            async_add_entities(new)

    _add()
    entry.async_on_unload(coordinator.async_add_listener(_add))


class FreeboxDeviceStatusSensor(FreeboxDeviceEntity, SensorEntity):
    """
    Un seul capteur par appareil réseau.
    State : 'online' | 'offline'
    Attributes : toutes les informations utiles
    """

    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator: FreeboxNetworkCoordinator,
                 entry: ConfigEntry, mac: str) -> None:
        super().__init__(coordinator, entry, mac)
        d = coordinator.data.get(mac, {})
        slug = d.get("slug", mac.replace(":", "_").lower())
        self._attr_unique_id = f"{DOMAIN}_{mac}_status"
        self.entity_id = f"sensor.{DOMAIN}_{slug}"

    @property
    def name(self) -> str:
        return "Statut"

    @property
    def native_value(self) -> str:
        return "online" if self._device_data.get("reachable") else "offline"

    @property
    def icon(self) -> str:
        return "mdi:lan-connect" if self._device_data.get("reachable") else "mdi:lan-disconnect"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._device_data

        def fmt(val: Any) -> str | None:
            if isinstance(val, datetime):
                return val.isoformat()
            return val

        return {
            "mac":              d.get("mac"),
            "ipv4":             d.get("ipv4"),
            "ipv6":             d.get("ipv6"),
            "ip_list":          d.get("ip_list", []),
            "ip_count":         d.get("ip_count"),
            "vendor":           d.get("vendor") or None,
            "hostname":         d.get("primary_name") or None,
            "alias":            d.get("alias") or None,
            "host_type":        d.get("host_type_label") or None,
            "domain_name":      d.get("domain_name") or None,
            "access_point_mac": d.get("ap_mac") or None,
            "ap_speed_mbps":    d.get("ap_speed") or None,
            "reachable":        d.get("reachable"),
            "active":           d.get("active"),
            "persistent":       d.get("persistent"),
            "first_seen":       fmt(d.get("first_activity")),
            "last_seen":        fmt(d.get("last_seen")),
            "last_activity":    fmt(d.get("last_activity")),
        }


class FreeboxGlobalSensor(CoordinatorEntity[FreeboxNetworkCoordinator], SensorEntity):
    """Capteur global rattaché au device hub."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "appareils"

    def __init__(self, coordinator, entry, key, label, icon, value_fn):
        super().__init__(coordinator)
        self._entry    = entry
        self._key      = key
        self._label    = label
        self._icon     = icon
        self._value_fn = value_fn
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{key}"
        self.entity_id = f"sensor.{DOMAIN}_{key}"

    @property
    def name(self) -> str:
        return self._label

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def native_value(self) -> Any:
        return self._value_fn(self.coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Freebox Network Inventory",
            manufacturer=MANUFACTURER,
            model="Hub v2.0.0",
            entry_type=DeviceEntryType.SERVICE,
        )
