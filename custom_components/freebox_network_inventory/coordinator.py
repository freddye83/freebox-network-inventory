"""Data coordinator for Freebox Network Inventory."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_ACTIVE, ATTR_ALIAS, ATTR_CONNECTION_TYPE, ATTR_HOST_TYPE,
    ATTR_INTERFACE, ATTR_IP_LIST, ATTR_LAST_ACTIVITY, ATTR_LAST_SEEN,
    ATTR_MAC, ATTR_PERSISTENT, ATTR_PRIMARY_NAME, ATTR_REACHABLE, ATTR_VENDOR,
    ATTR_STATIC_COMMENT, ATTR_STATIC_IP, ATTR_STATIC_LEASE,
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


def _recency_key(conn: dict[str, Any]) -> tuple:
    """Clé de tri : joignable d'abord, puis activité la plus récente."""
    return (
        bool(conn.get("reachable")),
        int(conn.get("last_activity") or 0),
        int(conn.get("last_time_reachable") or 0),
    )


def _pick_ip(l3: list[dict[str, Any]], family: str) -> str | None:
    """Retourne l'IP la plus pertinente pour une famille (ipv4 / ipv6).

    La Freebox conserve les anciens baux dans l3connectivities : on choisit
    l'adresse joignable avec la dernière activité la plus récente.
    Pour l'IPv6, on préfère une adresse globale à une link-local (fe80::).
    """
    candidates = [c for c in l3 if c.get("af") == family and c.get("addr")]
    if not candidates:
        return None
    if family == "ipv6":
        best = max(
            candidates,
            key=lambda c: (
                not c["addr"].lower().startswith("fe80"),
                *_recency_key(c),
            ),
        )
    else:
        best = max(candidates, key=_recency_key)
    return best["addr"]


def _parse_host(host: dict[str, Any]) -> dict[str, Any]:
    """Parse a raw Freebox LAN host into a clean dict."""
    mac = host.get("l2ident", {}).get("id", "").upper()

    # IPs — triées de la plus récente à la plus ancienne
    l3 = [c for c in host.get("l3connectivities", []) if c.get("addr")]
    l3_sorted = sorted(l3, key=_recency_key, reverse=True)
    ip_list: list[str] = [c["addr"] for c in l3_sorted]
    ipv4 = _pick_ip(l3, "ipv4")
    ipv6 = _pick_ip(l3, "ipv6")

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

    def __init__(self, hass: HomeAssistant, api: FreeboxApi, scan_interval: int,
                 config_entry: ConfigEntry | None = None) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=config_entry,
                         update_interval=timedelta(seconds=scan_interval))
        self.api = api
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._known_macs: set[str] = set()
        self._new_devices_since_last_check: list[dict[str, Any]] = []
        # Baux DHCP statiques indexés par MAC (majuscules)
        self.static_leases: dict[str, dict[str, Any]] = {}
        self.dhcp_config: dict[str, Any] = {}

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

        await self._async_refresh_static_leases()

        devices: dict[str, dict[str, Any]] = {}
        new_devices: list[dict[str, Any]] = []

        for raw in raw_hosts:
            parsed = _parse_host(raw)
            mac = parsed[ATTR_MAC]
            if not mac:
                continue
            lease = self.static_leases.get(mac)
            parsed[ATTR_STATIC_LEASE]   = lease is not None
            parsed[ATTR_STATIC_IP]      = lease.get("ip") if lease else None
            parsed[ATTR_STATIC_COMMENT] = (lease.get("comment") or None) if lease else None
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

    async def _async_refresh_static_leases(self) -> None:
        """Récupère les baux statiques + config DHCP.

        Non bloquant : en cas d'échec (droits insuffisants, firmware ancien…)
        on garde les dernières valeurs connues et l'inventaire continue.
        """
        try:
            leases = await self.api.get_static_leases()
            self.static_leases = {
                (l.get("mac") or "").upper(): {
                    "id":       l.get("id") or l.get("mac"),
                    "mac":      (l.get("mac") or "").upper(),
                    "ip":       l.get("ip"),
                    "comment":  l.get("comment") or "",
                    "hostname": l.get("hostname") or "",
                }
                for l in leases if l.get("mac")
            }
        except FreeboxApiError as err:
            _LOGGER.debug("Static leases unavailable: %s", err)
        try:
            self.dhcp_config = await self.api.get_dhcp_config()
        except FreeboxApiError as err:
            _LOGGER.debug("DHCP config unavailable: %s", err)

    def static_leases_list(self) -> list[dict[str, Any]]:
        """Liste des baux statiques enrichie avec l'inventaire (nom, état)."""
        out: list[dict[str, Any]] = []
        for mac, lease in self.static_leases.items():
            dev = (self.data or {}).get(mac, {})
            out.append({
                "mac":      mac,
                "ip":       lease.get("ip"),
                "comment":  lease.get("comment") or None,
                "hostname": lease.get("hostname") or None,
                "name":     dev.get("friendly_name") or lease.get("comment") or lease.get("hostname") or mac,
                "online":   bool(dev.get(ATTR_REACHABLE)) if dev else False,
                "known":    bool(dev),
            })

        def _ip_key(item: dict[str, Any]) -> tuple:
            try:
                return tuple(int(x) for x in (item.get("ip") or "").split("."))
            except ValueError:
                return (999,)

        return sorted(out, key=_ip_key)

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