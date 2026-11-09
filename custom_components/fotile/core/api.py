"""Fotile cloud API client (single endpoint, namespace dispatch)."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import aiohttp

from ..const import (
    API_BASE_URL,
    API_PATH,
    CODE_DEVICE_OFFLINE,
    CORP_ID,
    FAN_LEVEL_HIGH,
    FAN_LEVEL_STANDBY,
    GRANT_TYPE_OAUTH2_AUTH_CODE,
    KEY_COMMAND,
    KEY_DATA,
    KEY_DEVICES,
    KEY_SERVICE_ID,
    KEY_THIRD_PARTY_DEV_IDS,
    NS_ACCEPT_GRANT,
    NS_DEVICE_COMMAND,
    NS_DEVICE_DISCOVERY,
    NS_DEVICE_SNAPSHOT,
    SID_FAN_LEVEL,
    SID_LIGHT,
    SID_POWER_SWITCH,
    SWITCH_OFF_VALUE,
    SWITCH_ON_VALUE,
)
from .authbase import (
    AbstractAuth,
    FotileApiError,
    FotileAuthError,
    NoAuth,
    StaticTokenAuth,
)
from .mapping import (
    FotileProtocolError,
    error_description,
    find_snapshot_device,
    is_auth_error_code,
    is_success,
    map_device_fields,
    map_status_fields,
    parse_envelope,
    payload_code,
    to_bool,
)

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "AbstractAuth",
    "FotileApiError",
    "FotileAuthError",
    "FotileBusinessError",
    "FotileClient",
    "FotileConnectionError",
    "NoAuth",
    "StaticTokenAuth",
    "is_ha_config_entry_exception",
]


class FotileConnectionError(FotileApiError):
    """Network connection error."""


class FotileBusinessError(FotileApiError):
    """Business error returned by Fotile (payload.code != 0)."""

    def __init__(self, code: int | None, description: str) -> None:
        self.code = code
        self.description = description
        super().__init__(200, f"Fotile business error code={code}: {description}")


def is_ha_config_entry_exception(err: BaseException) -> bool:
    """True for HA config-entry lifecycle exceptions (must propagate)."""
    try:
        from homeassistant.exceptions import (  # noqa: PLC0415
            ConfigEntryAuthFailed,
            ConfigEntryNotReady,
        )
    except ImportError:  # pragma: no cover
        return False

    return isinstance(err, (ConfigEntryAuthFailed, ConfigEntryNotReady))


class FotileClient:
    """Thin client for the Fotile cloud-cloud API."""

    def __init__(
        self,
        auth: AbstractAuth,
        session: aiohttp.ClientSession | None = None,
        base_url: str = API_BASE_URL,
        corp_id: str = CORP_ID,
    ) -> None:
        self._auth = auth
        self._session = session or aiohttp.ClientSession()
        # Only close a session we created; HA's shared session is managed by HA.
        self._owns_session = session is None
        self._base_url = base_url.rstrip("/")
        self._corp_id = corp_id
        # thirdPartyUserId from AcceptGrant; attached to subsequent headers.
        self._third_party_user_id: str | None = None

    @property
    def auth(self) -> AbstractAuth:
        return self._auth

    @property
    def session(self) -> aiohttp.ClientSession:
        return self._session

    @property
    def third_party_user_id(self) -> str | None:
        return self._third_party_user_id

    def set_third_party_user_id(self, value: str | None) -> None:
        self._third_party_user_id = value

    # ---- envelope & unified request ----

    def _build_header(self, namespace: str) -> dict[str, Any]:
        header: dict[str, Any] = {
            "namespace": namespace,
            "thirdPartyId": self._corp_id,
            # granteeId == thirdPartyId (spec 2.1.4.1).
            "granteeId": self._corp_id,
            "messageId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
        }
        if self._third_party_user_id:
            header["thirdPartyUserId"] = self._third_party_user_id
        return header

    async def _call(
        self,
        namespace: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send one request and return the verified payload."""
        url = f"{self._base_url}{API_PATH}"
        body = {
            "header": self._build_header(namespace),
            "payload": payload if payload is not None else {},
        }

        try:
            response = await self._auth.async_request(
                self._session,
                "POST",
                url,
                json=body,
                headers={"Content-Type": "application/json"},
            )

            # HTTP 401 double-check (servers may always return 200).
            if response.status == 401:
                text = await response.text()
                raise FotileAuthError(401, f"Unauthorized: {text[:200]}")

            if response.status >= 400:
                text = await response.text()
                raise FotileApiError(response.status, text[:500])

            # Skip aiohttp's Content-Type check: the server may return
            # non-JSON content types with valid JSON bodies. Let parse_envelope
            # decide, so a wrong content type becomes a visible API error
            # instead of a silent "connection error" retry loop.
            raw = await response.json(content_type=None)

        except aiohttp.ClientError as err:
            # HA's OAuth2 token errors subclass aiohttp.ClientError for
            # backwards compatibility; they must propagate unchanged.
            if is_ha_config_entry_exception(err):
                raise
            raise FotileConnectionError(0, f"Connection error: {err}") from err

        try:
            _header, resp_payload = parse_envelope(raw)
        except FotileProtocolError as err:
            raise FotileApiError(response.status, str(err)) from err

        code = payload_code(resp_payload)
        if not is_success(resp_payload):
            description = error_description(resp_payload)
            _LOGGER.warning(
                "Fotile API %s business error code=%s description=%s",
                namespace,
                code,
                description,
            )
            if is_auth_error_code(code):
                raise FotileAuthError(
                    401,
                    f"Fotile credentials invalid code={code}: {description}",
                    code=code,
                )
            raise FotileBusinessError(code, description)

        return resp_payload

    # ---- AcceptGrant (spec 2.3.3) ----

    async def accept_grant(self) -> str | None:
        """Establish the account grant; required by every other namespace."""
        payload = {"grant": {"type": GRANT_TYPE_OAUTH2_AUTH_CODE}}
        resp = await self._call(NS_ACCEPT_GRANT, payload)

        user_id = resp.get("thirdPartyUserId")
        if user_id is not None:
            user_id = str(user_id)
        self._third_party_user_id = user_id

        if user_id is None:
            _LOGGER.warning(
                "AcceptGrant response missing thirdPartyUserId; "
                "subsequent requests will omit it"
            )
        else:
            _LOGGER.info("AcceptGrant succeeded, thirdPartyUserId = %s", user_id)

        return user_id

    # ---- DeviceDiscovery (spec 2.3.4) ----

    async def get_devices(self) -> list[dict[str, Any]]:
        """List all bound devices. No online status or firmware version."""
        resp = await self._call(NS_DEVICE_DISCOVERY, {})

        devices: list[dict[str, Any]] = []
        for raw in resp.get(KEY_DEVICES) or []:
            mapped = map_device_fields(raw)
            device_id = mapped.get("device_id")
            if not device_id:
                _LOGGER.warning("Skipping device without thirdPartyDevId: %s", raw)
                continue
            devices.append(
                {
                    "device_id": str(device_id),
                    "name": mapped.get("name") or str(device_id),
                    "device_type": mapped.get("device_type") or "",
                    "model": mapped.get("model") or "",
                    "manufacturer": mapped.get("manufacturer") or "",
                    "product_id": mapped.get("product_id") or "",
                    "serial_number": mapped.get("serial_number") or "",
                    "service_ids": mapped.get("service_ids") or [],
                    "service_types": mapped.get("service_types") or [],
                    "online": False,  # backfilled by snapshot
                    "_raw": mapped.get("_raw"),
                }
            )

        return devices

    # ---- DeviceSnapshot (spec 2.3.6) ----

    async def get_device_status(self, device_id: str) -> dict[str, Any]:
        """Snapshot for one device (spec requires a single id).

        Returns mapped internal fields plus online, _flat, _fetched_at.
        """
        payload = {KEY_THIRD_PARTY_DEV_IDS: [device_id]}
        resp = await self._call(NS_DEVICE_SNAPSHOT, payload)

        target = find_snapshot_device(resp, device_id)
        if target is None:
            _LOGGER.warning(
                "Device %s not found in snapshot (response had %d device(s))",
                device_id,
                len(resp.get(KEY_DEVICES) or []),
            )
            return {"online": False, "_flat": {}, "_fetched_at": time.time()}

        status = map_status_fields(target)
        status["_fetched_at"] = time.time()
        return status

    # ---- DeviceCommand (spec 2.3.7) ----

    async def send_command(
        self,
        device_id: str,
        sid: str,
        data: dict[str, Any],
        prod_id: str | None = None,
    ) -> dict[str, Any]:
        """Write a property. Timestamp uses yyyyMMddTHHmmssZ (no millis)."""
        command: dict[str, Any] = {
            "timestamp": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
            "thirdPartyDevId": device_id,
            KEY_SERVICE_ID: sid,
            KEY_DATA: data,
        }
        if prod_id:
            command["prodId"] = prod_id

        return await self._call(NS_DEVICE_COMMAND, {KEY_COMMAND: command})

    # ---- online check ----

    async def is_device_online(self, device_id: str) -> bool:
        try:
            status = await self.get_device_status(device_id)
        except FotileBusinessError as err:
            if err.code == CODE_DEVICE_OFFLINE:
                return False
            raise
        return to_bool(status.get("online"), default=False)

    # ---- category convenience methods (confirmed thing model, 2026-10) ----

    async def set_property(
        self,
        device_id: str,
        sid: str,
        attr: str,
        value: Any,
        prod_id: str | None = None,
    ) -> dict[str, Any]:
        return await self.send_command(device_id, sid, {attr: value}, prod_id)

    async def turn_on(
        self, device_id: str, prod_id: str | None = None
    ) -> dict[str, Any]:
        """PowerSwitch = 1."""
        return await self.set_property(
            device_id, SID_POWER_SWITCH, SID_POWER_SWITCH, SWITCH_ON_VALUE, prod_id
        )

    async def turn_off(
        self, device_id: str, prod_id: str | None = None
    ) -> dict[str, Any]:
        """PowerSwitch = 0."""
        return await self.set_property(
            device_id, SID_POWER_SWITCH, SID_POWER_SWITCH, SWITCH_OFF_VALUE, prod_id
        )

    async def set_fan_level(
        self, device_id: str, level: int, prod_id: str | None = None
    ) -> dict[str, Any]:
        """FanLevel 0-3. Rejects out-of-range locally."""
        if not FAN_LEVEL_STANDBY <= level <= FAN_LEVEL_HIGH:
            raise ValueError(
                f"FanLevel must be {FAN_LEVEL_STANDBY}-{FAN_LEVEL_HIGH}, got {level}"
            )
        return await self.set_property(
            device_id, SID_FAN_LEVEL, SID_FAN_LEVEL, level, prod_id
        )

    async def set_light(
        self, device_id: str, on: bool, prod_id: str | None = None
    ) -> dict[str, Any]:
        """Light = 1/0."""
        return await self.set_property(
            device_id,
            SID_LIGHT,
            SID_LIGHT,
            SWITCH_ON_VALUE if on else SWITCH_OFF_VALUE,
            prod_id,
        )

    # ---- teardown ----

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
