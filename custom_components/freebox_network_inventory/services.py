"""Services for Freebox Network Inventory — baux DHCP statiques."""
from __future__ import annotations

import ipaddress
import logging
import re

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv

from .const import (
    DATA_API,
    DATA_COORDINATOR,
    DOMAIN,
    SERVICE_REMOVE_STATIC_LEASE,
    SERVICE_SET_STATIC_LEASE,
)
from .coordinator import FreeboxNetworkCoordinator
from .freebox_api import FreeboxApi, FreeboxApiError

_LOGGER = logging.getLogger(__name__)

ATTR_ENTRY_ID = "config_entry_id"
ATTR_MAC = "mac"
ATTR_IP = "ip"
ATTR_COMMENT = "comment"

_MAC_RE = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")


def _mac(value: str) -> str:
    mac = str(value).strip().upper().replace("-", ":")
    if not _MAC_RE.match(mac):
        raise vol.Invalid(f"Invalid MAC address: {value}")
    return mac


def _ipv4(value: str) -> str:
    try:
        return str(ipaddress.IPv4Address(str(value).strip()))
    except ValueError as err:
        raise vol.Invalid(f"Invalid IPv4 address: {value}") from err


SET_SCHEMA = vol.Schema({
    vol.Required(ATTR_MAC): _mac,
    vol.Required(ATTR_IP): _ipv4,
    vol.Optional(ATTR_COMMENT): cv.string,
    vol.Optional(ATTR_ENTRY_ID): cv.string,
})

REMOVE_SCHEMA = vol.Schema({
    vol.Required(ATTR_MAC): _mac,
    vol.Optional(ATTR_ENTRY_ID): cv.string,
})


def _get_runtime(hass: HomeAssistant, call: ServiceCall) -> tuple[FreeboxApi, FreeboxNetworkCoordinator]:
    entries: dict = hass.data.get(DOMAIN, {})
    if not entries:
        raise ServiceValidationError("Freebox Network Inventory is not set up")
    entry_id = call.data.get(ATTR_ENTRY_ID)
    if entry_id:
        if entry_id not in entries:
            raise ServiceValidationError(f"Unknown config entry: {entry_id}")
        data = entries[entry_id]
    else:
        data = next(iter(entries.values()))
    return data[DATA_API], data[DATA_COORDINATOR]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Enregistre les services (une seule fois pour toutes les entrées)."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_STATIC_LEASE):
        return

    async def _set_static_lease(call: ServiceCall) -> None:
        api, coordinator = _get_runtime(hass, call)
        mac, ip = call.data[ATTR_MAC], call.data[ATTR_IP]

        # IP déjà réservée pour un autre appareil ?
        for other_mac, lease in coordinator.static_leases.items():
            if lease.get("ip") == ip and other_mac != mac:
                raise ServiceValidationError(
                    f"{ip} is already reserved for {other_mac}"
                )

        existing = coordinator.static_leases.get(mac)
        # Commentaire absent → on conserve celui du bail existant
        comment = call.data.get(ATTR_COMMENT, (existing or {}).get("comment") or "")
        try:
            if existing and existing.get("ip") == ip:
                # Même IP : on ne met à jour que le commentaire
                await api.update_static_lease(existing["id"], {"comment": comment})
            else:
                # Nouvelle IP : la Freebox ne permet pas de changer l'IP d'un bail
                # de façon fiable → suppression puis recréation
                if existing:
                    await api.delete_static_lease(existing["id"])
                try:
                    await api.add_static_lease(mac, ip, comment)
                except FreeboxApiError:
                    if existing:
                        # Restaure l'ancien bail pour ne pas le perdre
                        try:
                            await api.add_static_lease(mac, existing["ip"], existing.get("comment") or "")
                        except FreeboxApiError:
                            _LOGGER.error("Could not restore previous static lease %s → %s", mac, existing["ip"])
                        await coordinator.async_request_refresh()
                    raise
        except FreeboxApiError as err:
            raise HomeAssistantError(f"Freebox refused the static lease: {err}") from err

        _LOGGER.info("Static lease set: %s → %s (%s)", mac, ip, comment)
        await coordinator.async_request_refresh()

    async def _remove_static_lease(call: ServiceCall) -> None:
        api, coordinator = _get_runtime(hass, call)
        mac = call.data[ATTR_MAC]
        existing = coordinator.static_leases.get(mac)
        if not existing:
            raise ServiceValidationError(f"No static lease for {mac}")
        try:
            await api.delete_static_lease(existing["id"])
        except FreeboxApiError as err:
            raise HomeAssistantError(f"Freebox refused the deletion: {err}") from err

        _LOGGER.info("Static lease removed: %s", mac)
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_SET_STATIC_LEASE, _set_static_lease, schema=SET_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_STATIC_LEASE, _remove_static_lease, schema=REMOVE_SCHEMA)


def async_unload_services(hass: HomeAssistant) -> None:
    """Supprime les services quand la dernière entrée est déchargée."""
    if hass.data.get(DOMAIN):
        return
    for svc in (SERVICE_SET_STATIC_LEASE, SERVICE_REMOVE_STATIC_LEASE):
        hass.services.async_remove(DOMAIN, svc)
