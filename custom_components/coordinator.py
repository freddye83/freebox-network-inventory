"""Data coordinator for Freebox Network Inventory."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_ACTIVE, ATTR_ALIAS, ATTR_CONNECTION_TYPE, ATTR_HOST_TYPE,
    ATTR_INTERFACE, ATTR_IP_LIST, ATTR_LAST_ACTIVITY, ATTR_LAST_SEEN,
    ATTR_MAC, ATTR_PERSISTENT, ATTR_PRIMARY_NAME, ATTR_REACHABLE, ATTR_VENDOR,
    DOMAIN, EVENT_NEW_DEVICE, HOST_TYPE_LABELS, STORAGE_KEY, STORAGE_VERSION,
)
from .freebox_api import FreeboxApi, FreeboxApiError

_LOGGER = logging.getLogger(__name__)


def _ts(val: Any) -> datetime | None:
    """Unix int → datetime aware UTC."""
    if not val:
        return None
    try:
        ts = int(val)
        return datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
    except (ValueError, TypeError, OSError):
        return None


def _slug(name: str) -> str:
    """Convert a friendly name to a HA-compatible slug."""
    s = name.lower().strip()
    s = re.sub(r"[àáâãäå]", "a", s)
    s = re.sub(r"[èéêë]", "e", s)
    s = re.sub(r"[ìíîï]", "i", s)
    s = re.sub(r"[òóôõö]", "o", s)
    s = re.sub(r"[ùúûü]", "u", s)
    s = re.sub(r"[ç]", "c", s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "device"


def _parse_host(host: dict[str, Any]) -> dict[str, Any]:
    """Parse a raw Freebox LAN host into a clean dict."""
    mac = host.get("l2ident", {}).get("id", "").upper()

    # IPs
    l3 = host.get("l3connectivities", [])
    ip_list: list[str] = [c["addr"] for c in l3 if c.get("addr")]
    ipv4 = next((ip for ip in ip_list if "." in ip), None)
    ipv6 = next((ip for ip in ip_list if ":" in ip), None)

    # Access point
    ap = host.get("access_point", {})
    ap_mac = ap.get("mac", "")
    ap_eth = ap.get("ethernet_information", {})
    ap_speed = ap_eth.get("speed")

    # Host type
    host_type_raw = host.get("host_type", "")
    host_type_label = HOST_TYPE_LABELS.get(host_type_raw, host_type_raw)

    # Primary name
    primary_name = host.get("primary_name", "")
    if not primary_name:
        for n in host.get("names", []):
            if n.get("source") in ("mdns", "netbios", "dhcp"):
                primary_name = n.get("name", "")
                break
    alias = host.get("primary_name", "") or primary_name
    friendly = alias or primary_name or mac

    # Slug pour entity_id (préfixé dans les entités)
    mac_slug = mac.replace(":", "_").lower()

    return {
        ATTR_MAC:             mac,
        ATTR_ALIAS:           alias,
        ATTR_PRIMARY_NAME:    primary_name,
        ATTR_VENDOR:          host.get("vendor_name", ""),
        ATTR_REACHABLE:       bool(host.get("reachable", False)),
        ATTR_ACTIVE:          bool(host.get("active", False)),
        ATTR_PERSISTENT:      bool(host.get("persistent", False)),
        ATTR_INTERFACE:       "",
        ATTR_IP_LIST:         ip_list,
        ATTR_LAST_ACTIVITY:   _ts(host.get("last_activity", 0)),
        ATTR_LAST_SEEN:       _ts(host.get("last_time_reachable", 0)),
        ATTR_CONNECTION_TYPE: "",
        ATTR_HOST_TYPE:       host_type_raw,
        # Enriched
        "host_type_label":  host_type_label,
        "domain_name":      host.get("domain_name", ""),
        "ap_mac":           ap_mac,
        "ap_speed":         ap_speed,
        "first_activity":   _ts(host.get("first_activity", 0)),
        "ip_count":         len(ip_list),
        "ipv4":             ipv4,
        "ipv6":             ipv6,
        "friendly_name":    friendly,
        "slug":             _slug(friendly),
        "mac_slug":         mac_slug,
        "raw":              host,   # conservé pour PUT /lan/browser/pub/{id}
    }


class FreeboxNetworkCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator that polls the Freebox LAN browser."""

    def __init__(self, hass: HomeAssistant, api: FreeboxApi, scan_interval: int) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_interval=timedelta(seconds=scan_interval))
        self.api = api
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._known_macs: set[str] = set()
        self._new_devices_since_last_check: list[dict[str, Any]] = []

    async def async_load_known_devices(self) -> None:
        data = await self._store.async_load()
        if data and "known_macs" in data:
            self._known_macs = set(data["known_macs"])

    async def _save_known_devices(self) -> None:
        await self._store.async_save({"known_macs": list(self._known_macs)})

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            raw_hosts = await self.api.get_lan_hosts()
        except FreeboxApiError as err:
            raise UpdateFailed(f"Error fetching Freebox LAN hosts: {err}") from err

        devices: dict[str, dict[str, Any]] = {}
        new_devices: list[dict[str, Any]] = []

        for raw in raw_hosts:
            parsed = _parse_host(raw)
            mac = parsed[ATTR_MAC]
            if not mac:
                continue
            devices[mac] = parsed
            if mac not in self._known_macs:
                new_devices.append(parsed)
                self._known_macs.add(mac)

        if new_devices:
            self._new_devices_since_last_check = new_devices
            await self._save_known_devices()
            for device in new_devices:
                await self._notify_new_device(device)
                self.hass.bus.async_fire(EVENT_NEW_DEVICE, {
                    "mac":       device[ATTR_MAC],
                    "name":      device["friendly_name"],
                    "vendor":    device[ATTR_VENDOR],
                    "ip":        device.get("ipv4") or "",
                    "host_type": device.get("host_type_label") or "",
                })
        else:
            self._new_devices_since_last_check = []

        return devices

    async def _notify_new_device(self, device: dict[str, Any]) -> None:
        name   = device["friendly_name"]
        mac    = device[ATTR_MAC]
        vendor = device[ATTR_VENDOR] or "Inconnu"
        ip     = device.get("ipv4") or device.get("ipv6") or "N/A"
        dtype  = device.get("host_type_label") or "Inconnu"
        persistent_notification.async_create(
            self.hass,
            message=(
                f"**Nom :** {name}\n"
                f"**MAC :** {mac}\n"
                f"**Fabricant :** {vendor}\n"
                f"**Type :** {dtype}\n"
                f"**IP :** {ip}"
            ),
            title="🔍 Nouvel équipement réseau détecté",
            notification_id=f"{DOMAIN}_new_{mac.replace(':', '_')}",
        )

    @property
    def new_device_count(self) -> int:
        return len(self._new_devices_since_last_check)

    def get_stats(self) -> dict[str, Any]:
        if not self.data:
            return {"total": 0, "online": 0, "offline": 0, "unknown_vendor": 0}
        total  = len(self.data)
        online = sum(1 for d in self.data.values() if d[ATTR_REACHABLE])
        return {
            "total":          total,
            "online":         online,
            "offline":        total - online,
            "unknown_vendor": sum(1 for d in self.data.values() if not d[ATTR_VENDOR]),
        }
