"""Coordinateur dédié au switch Freebox — polling toutes les 30s."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .freebox_api import FreeboxApi, FreeboxApiError

_LOGGER = logging.getLogger(__name__)

FREEBOX_SWITCH_STATUS_URL = "/switch/status/"
FREEBOX_SWITCH_PORT_STATS_URL = "/switch/port/{id}/stats"

SWITCH_SCAN_INTERVAL = 30  # secondes


class FreeboxSwitchCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Coordinateur pour le switch Freebox.

    Données indexées par numéro de port :
    {
        1: {
            "id": 1,
            "link": "up",
            "duplex": "full",
            "speed": "1000",
            "mode": "1000BaseT-FD",
            "mac_list": [{"mac": "...", "hostname": "..."}],
            "stats": { rx_bytes_rate, tx_bytes_rate, rx_err_packets, ... }
        },
        ...
    }
    """

    def __init__(self, hass: HomeAssistant, api: FreeboxApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_switch",
            update_interval=timedelta(seconds=SWITCH_SCAN_INTERVAL),
        )
        self.api = api

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Récupère le statut et les stats de tous les ports switch."""
        try:
            # 1. Statut global
            status_list = await self.api.get_switch_status()
        except FreeboxApiError as err:
            raise UpdateFailed(f"Erreur switch status: {err}") from err

        result: dict[int, dict[str, Any]] = {}

        for port in status_list:
            port_id = port.get("id")
            if port_id is None:
                continue

            entry: dict[str, Any] = {
                "id":       port_id,
                "link":     port.get("link", "down"),
                "duplex":   port.get("duplex", "unknown"),
                "speed":    port.get("speed", "0"),
                "mode":     port.get("mode", ""),
                "mac_list": port.get("mac_list", []),
                "stats":    {},
            }

            # 2. Stats détaillées par port (seulement si lien actif)
            if entry["link"] == "up":
                try:
                    stats = await self.api.get_switch_port_stats(port_id)
                    entry["stats"] = stats
                except FreeboxApiError as err:
                    _LOGGER.debug("Stats port %d indisponibles: %s", port_id, err)

            result[port_id] = entry

        _LOGGER.debug("Switch: %d ports récupérés", len(result))
        return result