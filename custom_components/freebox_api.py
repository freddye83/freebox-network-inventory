"""Freebox API client for Freebox Network Inventory."""
from __future__ import annotations

import hashlib
import hmac
import logging
import ssl
from typing import Any

import aiohttp

from .const import (
    FREEBOX_API_BASE,
    FREEBOX_API_VERSION_URL,
    FREEBOX_APP_ID,
    FREEBOX_APP_NAME,
    FREEBOX_APP_VERSION,
    FREEBOX_AUTHORIZE_URL,
    FREEBOX_DEVICE_NAME,
    FREEBOX_LAN_BROWSER_URL,
    FREEBOX_LOGIN_URL,
    FREEBOX_SESSION_URL,
)

_LOGGER = logging.getLogger(__name__)


class FreeboxApiError(Exception):
    """Freebox API error."""


class FreeboxAuthError(FreeboxApiError):
    """Freebox authentication error."""


class FreeboxApi:
    """Async Freebox API client."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._session: aiohttp.ClientSession | None = None
        self._app_token: str | None = None
        self._session_token: str | None = None
        self._api_version: str = "v8"
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    @property
    def app_token(self) -> str | None:
        return self._app_token

    def set_app_token(self, token: str) -> None:
        self._app_token = token

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=self._ssl_context)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_base_url(self) -> str:
        return f"https://{self._host}:{self._port}{FREEBOX_API_BASE.format(version=self._api_version)}"

    async def _request(
        self,
        method: str,
        path: str,
        data: dict | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        session = await self._get_session()
        url = f"{self._get_base_url()}{path}"
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if authenticated and self._session_token:
            headers["X-Fbx-App-Auth"] = self._session_token

        try:
            async with session.request(
                method,
                url,
                json=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                result = await response.json()

                if not result.get("success", False):
                    error_code = result.get("error_code", "unknown")
                    msg = result.get("msg", "Unknown error")
                    if error_code in ("auth_required", "invalid_token"):
                        raise FreeboxAuthError(f"Auth error: {msg}")
                    raise FreeboxApiError(f"API error {error_code}: {msg}")

                return result.get("result", {})

        except aiohttp.ClientError as err:
            raise FreeboxApiError(f"Connection error: {err}") from err

    async def get_api_version(self) -> dict[str, Any]:
        session = await self._get_session()
        url = f"https://{self._host}:{self._port}{FREEBOX_API_VERSION_URL}"
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                data = await response.json()
                self._api_version = data.get("api_version", "8").split(".")[0]
                _LOGGER.debug("Freebox API version: v%s", self._api_version)
                return data
        except aiohttp.ClientError as err:
            raise FreeboxApiError(f"Cannot reach Freebox: {err}") from err

    async def authorize(self) -> tuple[str, str]:
        """Demande d'autorisation avec droits lecture + settings (modification LAN)."""
        result = await self._request(
            "POST",
            FREEBOX_AUTHORIZE_URL,
            data={
                "app_id":      FREEBOX_APP_ID,
                "app_name":    FREEBOX_APP_NAME,
                "app_version": FREEBOX_APP_VERSION,
                "device_name": FREEBOX_DEVICE_NAME,
                # Droits demandés :
                # - settings : lire/modifier les réglages (noms, types LAN hosts)
                # - lan :      accès au navigateur LAN
                "app_permissions": {
                    "settings": True,
                    "lan":      True,
                },
            },
            authenticated=False,
        )
        app_token = result["app_token"]
        track_id  = result["track_id"]
        self._app_token = app_token
        return app_token, str(track_id)

    async def get_authorization_status(self, track_id: str) -> str:
        result = await self._request(
            "GET",
            f"{FREEBOX_AUTHORIZE_URL}/{track_id}",
            authenticated=False,
        )
        return result.get("status", "unknown")

    async def open_session(self) -> None:
        if not self._app_token:
            raise FreeboxAuthError("No app token available")

        login_result = await self._request("GET", FREEBOX_LOGIN_URL, authenticated=False)
        challenge = login_result["challenge"]

        password = hmac.new(
            self._app_token.encode("utf-8"),
            challenge.encode("utf-8"),
            hashlib.sha1,
        ).hexdigest()

        session_result = await self._request(
            "POST",
            FREEBOX_SESSION_URL,
            data={
                "app_id":   FREEBOX_APP_ID,
                "password": password,
            },
            authenticated=False,
        )
        self._session_token = session_result["session_token"]
        _LOGGER.debug("Freebox session opened (permissions: %s)",
                      session_result.get("permissions", {}))

    async def close_session(self) -> None:
        if self._session_token:
            try:
                await self._request("POST", f"{FREEBOX_LOGIN_URL}/logout")
            except FreeboxApiError:
                pass
            self._session_token = None

    async def get_lan_hosts(self) -> list[dict[str, Any]]:
        """Retourne tous les hôtes LAN."""
        try:
            result = await self._request("GET", FREEBOX_LAN_BROWSER_URL)
            if isinstance(result, list):
                return result
            return []
        except FreeboxAuthError:
            _LOGGER.debug("Session expired, re-opening...")
            await self.open_session()
            result = await self._request("GET", FREEBOX_LAN_BROWSER_URL)
            return result if isinstance(result, list) else []

    async def update_lan_host(self, host_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Modifie un hôte LAN (nom, type). host_id = ex: 'ether-3c:0b:59:38:f6:f6'."""
        try:
            return await self._request(
                "PUT",
                f"{FREEBOX_LAN_BROWSER_URL}{host_id}",
                data=data,
            ) or {}
        except FreeboxAuthError:
            await self.open_session()
            return await self._request(
                "PUT",
                f"{FREEBOX_LAN_BROWSER_URL}{host_id}",
                data=data,
            ) or {}
