"""Sensors for Freebox Network Inventory."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_COORDINATOR,
    DATA_SWITCH_COORDINATOR,
    DOMAIN,
    MANUFACTURER,
    SENSOR_DEVICES_NEW,
    SENSOR_DEVICES_ONLINE,
    SENSOR_DEVICES_TOTAL,
    SENSOR_STATIC_LEASES,
)
from .coordinator import FreeboxNetworkCoordinator
from .entity_base import FreeboxDeviceEntity
from .switch_coordinator import FreeboxSwitchCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SwitchPortSensorDescription:
    key: str
    name: str
    icon: str
    value_fn: Callable[[dict[str, Any]], Any]
    state_class: SensorStateClass | None = None
    native_unit: str | None = None
    device_class: SensorDeviceClass | None = None


SWITCH_PORT_SENSOR_DESCRIPTIONS: tuple[SwitchPortSensorDescription, ...] = (
    SwitchPortSensorDescription(
        key="vitesse",
        name="Vitesse",
        icon="mdi:speedometer",
        value_fn=lambda d: f"{d.get('speed')} Mbps" if d.get("speed") and d.get("speed") != "0" else None,
    ),
    SwitchPortSensorDescription(
        key="mode",
        name="Mode",
        icon="mdi:ethernet",
        value_fn=lambda d: d.get("mode") or None,
    ),
    SwitchPortSensorDescription(
        key="duplex",
        name="Duplex",
        icon="mdi:swap-horizontal",
        value_fn=lambda d: d.get("duplex") or None,
    ),
    SwitchPortSensorDescription(
        key="appareils",
        name="Appareils connectés",
        icon="mdi:devices",
        state_class=SensorStateClass.MEASUREMENT,
        # state = nombre d'appareils (< 255 chars)
        # liste complète dans extra_state_attributes via FreeboxSwitchPortSensor
        value_fn=lambda d: len(d.get("mac_list", [])),
    ),

    SwitchPortSensorDescription(
        key="debit_rx",
        name="Débit entrant",
        icon="mdi:arrow-down",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit="B/s",
        device_class=SensorDeviceClass.DATA_RATE,
        value_fn=lambda d: d.get("stats", {}).get("rx_bytes_rate"),
    ),
    SwitchPortSensorDescription(
        key="debit_tx",
        name="Débit sortant",
        icon="mdi:arrow-up",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit="B/s",
        device_class=SensorDeviceClass.DATA_RATE,
        value_fn=lambda d: d.get("stats", {}).get("tx_bytes_rate"),
    ),
    SwitchPortSensorDescription(
        key="paquets_rx",
        name="Paquets reçus",
        icon="mdi:package-down",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("stats", {}).get("rx_good_packets"),
    ),
    SwitchPortSensorDescription(
        key="paquets_tx",
        name="Paquets envoyés",
        icon="mdi:package-up",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("stats", {}).get("tx_packets"),
    ),
    SwitchPortSensorDescription(
        key="erreurs_rx",
        name="Erreurs RX",
        icon="mdi:alert-circle-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("stats", {}).get("rx_err_packets"),
    ),
    SwitchPortSensorDescription(
        key="erreurs_fcs",
        name="Erreurs FCS",
        icon="mdi:alert-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("stats", {}).get("rx_fcs_packets"),
    ),
    SwitchPortSensorDescription(
        key="collisions_tx",
        name="Collisions TX",
        icon="mdi:car-crash",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("stats", {}).get("tx_collisions"),
    ),
    SwitchPortSensorDescription(
        key="octets_corrompus",
        name="Octets corrompus RX",
        icon="mdi:close-network",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("stats", {}).get("rx_bad_bytes"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: FreeboxNetworkCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    switch_coordinator: FreeboxSwitchCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_SWITCH_COORDINATOR]

    # ── Capteurs globaux Hub ──────────────────────────────────────────────────
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
        FreeboxStaticLeasesSensor(coordinator, entry, SENSOR_STATIC_LEASES,
                            "Baux statiques", "mdi:ip-network",
                            lambda c: len(c.static_leases),
                            unit="baux",
                            attrs_fn=lambda c: {
                                "leases":         c.static_leases_list(),
                                "dhcp_range_start": c.dhcp_config.get("ip_range_start"),
                                "dhcp_range_end":   c.dhcp_config.get("ip_range_end"),
                                "gateway":          c.dhcp_config.get("gateway"),
                                "netmask":          c.dhcp_config.get("netmask"),
                            }),
    ])

    # ── Capteurs appareils LAN — ajout dynamique ──────────────────────────────
    known_macs: set[str] = set()

    def _add_lan_sensors() -> None:
        if not coordinator.data:
            return
        new = [
            FreeboxDeviceStatusSensor(coordinator, entry, mac)
            for mac in coordinator.data if mac not in known_macs
        ]
        for e in new:
            known_macs.add(e._mac)
        if new:
            async_add_entities(new)

    _add_lan_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_lan_sensors))

    # ── Capteurs switch — ajout dynamique ─────────────────────────────────────
    # Utilise un listener pour éviter le timing issue au démarrage
    known_ports: set[int] = set()

    def _add_switch_sensors() -> None:
        if not switch_coordinator.data:
            return
        new_entities = []
        for port_id in switch_coordinator.data:
            if port_id not in known_ports:
                known_ports.add(port_id)
                for desc in SWITCH_PORT_SENSOR_DESCRIPTIONS:
                    new_entities.append(
                        FreeboxSwitchPortSensor(switch_coordinator, entry, port_id, desc)
                    )
        if new_entities:
            async_add_entities(new_entities)

    _add_switch_sensors()
    entry.async_on_unload(switch_coordinator.async_add_listener(_add_switch_sensors))


# ── Appareil LAN — capteur statut ─────────────────────────────────────────────

class FreeboxDeviceStatusSensor(FreeboxDeviceEntity, SensorEntity):
    """Un capteur par appareil réseau."""

    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator, entry, mac):
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
            "static_lease":     d.get("static_lease"),
            "static_ip":        d.get("static_ip"),
            "static_lease_comment": d.get("static_lease_comment"),
            "first_seen":       fmt(d.get("first_activity")),
            "last_seen":        fmt(d.get("last_seen")),
            "last_activity":    fmt(d.get("last_activity")),
        }


# ── Capteur global Hub ────────────────────────────────────────────────────────

class FreeboxGlobalSensor(CoordinatorEntity[FreeboxNetworkCoordinator], SensorEntity):
    """Capteur global rattaché au device hub."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "appareils"

    def __init__(self, coordinator, entry, key, label, icon, value_fn,
                 unit: str = "appareils", attrs_fn=None):
        super().__init__(coordinator)
        self._attrs_fn = attrs_fn
        self._attr_native_unit_of_measurement = unit

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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self._attrs_fn(self.coordinator) if self._attrs_fn else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Freebox Network Inventory",
            manufacturer=MANUFACTURER,
            model="Hub v1.2.0",
            entry_type=DeviceEntryType.SERVICE,
        )


class FreeboxStaticLeasesSensor(FreeboxGlobalSensor):
    """Nombre de baux DHCP statiques + liste complète en attribut `leases`."""

    # Liste potentiellement longue : pas d'historique dans le recorder
    _unrecorded_attributes = frozenset({"leases", "dhcp_range_start", "dhcp_range_end", "gateway", "netmask"})


# ── Capteurs switch ────────────────────────────────────────────────────────────

class FreeboxSwitchPortSensor(
    CoordinatorEntity[FreeboxSwitchCoordinator], SensorEntity
):
    """Capteur pour un attribut d'un port switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FreeboxSwitchCoordinator,
        entry: ConfigEntry,
        port_id: int,
        description: SwitchPortSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._port_id = port_id
        self._entry   = entry
        self._desc    = description
        self._attr_unique_id = f"{DOMAIN}_switch_port_{port_id}_{description.key}"
        self.entity_id = f"sensor.{DOMAIN}_switch_port_{port_id}_{description.key}"
        self._attr_icon = description.icon
        if description.state_class:
            self._attr_state_class = description.state_class
        if description.native_unit:
            self._attr_native_unit_of_measurement = description.native_unit
        if description.device_class:
            self._attr_device_class = description.device_class

    @property
    def _port_data(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get(self._port_id, {})
        return {}

    @property
    def name(self) -> str:
        return self._desc.name

    @property
    def native_value(self) -> Any:
        return self._desc.value_fn(self._port_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Pour le capteur appareils, expose la liste complète en attribut."""
        if self._desc.key == "appareils":
            mac_list = self._port_data.get("mac_list", [])
            return {
                "liste": [
                    {
                        "hostname": m.get("hostname") or m.get("mac", "?"),
                        "mac": m.get("mac", ""),
                    }
                    for m in mac_list
                ]
            }
        return None

    @property
    def available(self) -> bool:
        """Stats indisponibles si le port n'a pas de lien."""
        stats_keys = {
            "debit_rx", "debit_tx", "paquets_rx", "paquets_tx",
            "erreurs_rx", "erreurs_fcs", "collisions_tx", "octets_corrompus",
        }
        if self._desc.key in stats_keys:
            return self._port_data.get("link") == "up"
        return True

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"switch_port_{self._port_id}")},
            name=f"Switch Freebox — Port {self._port_id}",
            manufacturer=MANUFACTURER,
            model="Switch intégré",
            entry_type=DeviceEntryType.SERVICE,
        )