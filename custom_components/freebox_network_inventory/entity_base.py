"""Base entity for Freebox Network Inventory."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import FreeboxNetworkCoordinator


class FreeboxDeviceEntity(CoordinatorEntity[FreeboxNetworkCoordinator]):
    """Base entity tied to a MAC address device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FreeboxNetworkCoordinator,
        entry: ConfigEntry,
        mac: str,
    ) -> None:
        super().__init__(coordinator)
        self._mac   = mac
        self._entry = entry

    @property
    def _device_data(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get(self._mac, {})
        return {}

    @property
    def device_info(self) -> DeviceInfo:
        d = self._device_data
        vendor   = d.get("vendor") or None
        friendly = d.get("friendly_name") or self._mac
        model    = d.get("host_type_label") or "Network Device"

        # via_device pointe vers le hub uniquement s'il existe déjà dans le registry
        # On utilise l'entry_id comme identifiant du hub — mais on ne le référence
        # que si le device hub a déjà été enregistré (via FreeboxGlobalSensor).
        # Pour éviter le warning "non existing via_device", on omet via_device ici
        # et on laisse le hub se créer d'abord via le sensor global.
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=friendly,
            manufacturer=vendor,
            model=model,
            # via_device supprimé — causait un warning HA car le hub
            # n'existe pas encore au moment de la création des entités par appareil
        )

    def _fmt_dt(self, val: Any) -> str | None:
        """Format datetime to ISO string."""
        if isinstance(val, datetime):
            return val.isoformat()
        return val