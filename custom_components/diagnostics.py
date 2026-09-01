"""Diagnostics support for Freebox Network Inventory."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import FreeboxNetworkCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: FreeboxNetworkCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    stats = coordinator.get_stats()
    devices = coordinator.data or {}

    device_list = []
    for mac, data in devices.items():
        device_list.append(
            {
                "mac": mac,
                "name": data.get("friendly_name"),
                "vendor": data.get("vendor"),
                "reachable": data.get("reachable"),
                "interface": data.get("interface"),
                "connection_type": data.get("connection_type"),
                "ipv4": data.get("ipv4"),
                "ipv6": data.get("ipv6"),
                "last_seen": data.get("last_seen"),
            }
        )

    return {
        "summary": {
            "total_devices": stats["total"],
            "online": stats["online"],
            "offline": stats["offline"],
            "ethernet": stats["ethernet"],
            "wifi": stats["wifi"],
            "unknown_vendor": stats["unknown_vendor"],
            "new_devices_last_poll": coordinator.new_device_count,
        },
        "config": {
            "host": entry.data.get("host"),
            "port": entry.data.get("port"),
            "scan_interval": entry.options.get(
                "scan_interval", entry.data.get("scan_interval", 60)
            ),
        },
        "devices": device_list,
    }
