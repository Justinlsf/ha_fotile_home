"""Response parsing and field mapping (no aiohttp/HA deps)."""
from __future__ import annotations

from typing import Any

from ..const import (
    AUTH_ERROR_CODES,
    CODE_SUCCESS,
    DEVICE_STATUS_ONLINE,
    FIELD_MAP_DEVICE_INFO,
    FIELD_MAP_DEVICE_TOP,
    KEY_DATA,
    KEY_DEVICES,
    KEY_DESCRIPTION,
    KEY_SERVICE_ID,
    KEY_SERVICE_TYPE,
    KEY_SERVICES,
    KEY_STATUS,
    KEY_TIMESTAMP,
    MISSING_AUTH_CODES,
    RESPONSE_KEY_CODE,
    RESPONSE_KEY_HEADER,
    RESPONSE_KEY_PAYLOAD,
    STATUS_FIELD_MAP,
)

__all__ = [
    "FotileProtocolError",
    "extract_device_list",
    "extract_service_ids",
    "flatten_service_data",
    "is_auth_error_code",
    "map_device_fields",
    "map_status_fields",
    "parse_envelope",
    "payload_code",
    "to_bool",
    "to_float",
    "to_int",
]


class FotileProtocolError(Exception):
    """Response does not match the envelope contract."""


def parse_envelope(response: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a response into (header, payload). Missing side -> {}."""
    if not isinstance(response, dict):
        raise FotileProtocolError(
            f"Response is not a JSON object, got {type(response).__name__}"
        )

    payload = response.get(RESPONSE_KEY_PAYLOAD)
    if payload is None:
        raise FotileProtocolError("Response missing payload field")
    if not isinstance(payload, dict):
        raise FotileProtocolError(
            f"payload is not a JSON object, got {type(payload).__name__}"
        )

    header = response.get(RESPONSE_KEY_HEADER)
    if not isinstance(header, dict):
        header = {}

    return header, payload


def payload_code(payload: dict[str, Any]) -> int | None:
    """Extract the business code; None if missing or non-integer."""
    code = payload.get(RESPONSE_KEY_CODE)
    if isinstance(code, bool):  # bool is a subclass of int
        return None
    if isinstance(code, int):
        return code
    if isinstance(code, str):
        try:
            return int(code)
        except ValueError:
            return None
    return None


def is_success(payload: dict[str, Any]) -> bool:
    return payload_code(payload) == CODE_SUCCESS


def error_description(payload: dict[str, Any]) -> str:
    desc = payload.get(KEY_DESCRIPTION)
    return str(desc) if desc is not None else ""


def is_auth_error_code(code: int | None) -> bool:
    """True if the code indicates invalid credentials (trigger HA reauth)."""
    if code is None:
        return False
    return code in AUTH_ERROR_CODES or code in MISSING_AUTH_CODES


def extract_device_list(payload: dict[str, Any]) -> list[Any]:
    devices = payload.get(KEY_DEVICES)
    if not isinstance(devices, list):
        return []
    return devices


def extract_service_ids(device: dict[str, Any]) -> list[str]:
    """Capability declarations (services[].sid). Unique, order preserved."""
    if not isinstance(device, dict):
        return []
    services = device.get(KEY_SERVICES)
    if not isinstance(services, list):
        return []
    sids: list[str] = []
    for svc in services:
        if not isinstance(svc, dict):
            continue
        sid = svc.get(KEY_SERVICE_ID)
        if isinstance(sid, str) and sid and sid not in sids:
            sids.append(sid)
    return sids


def extract_service_types(device: dict[str, Any]) -> list[str]:
    """services[].st list, unique, order preserved."""
    if not isinstance(device, dict):
        return []
    services = device.get(KEY_SERVICES)
    if not isinstance(services, list):
        return []
    types: list[str] = []
    for svc in services:
        if not isinstance(svc, dict):
            continue
        st = svc.get(KEY_SERVICE_TYPE)
        if isinstance(st, str) and st and st not in types:
            types.append(st)
    return types


def map_device_fields(device: Any) -> dict[str, Any]:
    """Map a DeviceDiscovery device object to the internal structure."""
    if not isinstance(device, dict):
        return {
            "device_id": None,
            "name": None,
            "model": None,
            "device_type": None,
            "manufacturer": None,
            "product_id": None,
            "serial_number": None,
            "service_ids": [],
            "service_types": [],
            "_raw": device,
        }

    dev_info = device.get("devInfo")
    if not isinstance(dev_info, dict):
        dev_info = {}

    mapped: dict[str, Any] = {}
    for internal, api_key in FIELD_MAP_DEVICE_TOP.items():
        mapped[internal] = device.get(api_key)
    for internal, api_key in FIELD_MAP_DEVICE_INFO.items():
        mapped[internal] = dev_info.get(api_key)

    mapped["service_ids"] = extract_service_ids(device)
    mapped["service_types"] = extract_service_types(device)
    mapped["_raw"] = device
    return mapped


def flatten_service_data(services: Any) -> dict[str, Any]:
    """Flatten snapshot services[] to {"sid.attr": value}."""
    if not isinstance(services, list):
        return {}

    flat: dict[str, Any] = {}
    for svc in services:
        if not isinstance(svc, dict):
            continue
        sid = svc.get(KEY_SERVICE_ID)
        if not isinstance(sid, str) or not sid:
            continue

        ts = svc.get(KEY_TIMESTAMP)
        if ts is not None:
            flat[f"{sid}.__ts"] = ts

        data = svc.get(KEY_DATA)
        if not isinstance(data, dict):
            continue
        for attr, value in data.items():
            flat[f"{sid}.{attr}"] = value

    return flat


def map_status_fields(snapshot_device: Any) -> dict[str, Any]:
    """Map a snapshot device to the internal status dict."""
    result: dict[str, Any] = {"online": False, "_flat": {}}
    if not isinstance(snapshot_device, dict):
        return result

    status = snapshot_device.get(KEY_STATUS)
    result["online"] = (
        isinstance(status, str) and status.strip().lower() == DEVICE_STATUS_ONLINE
    )

    flat = flatten_service_data(snapshot_device.get(KEY_SERVICES))
    result["_flat"] = flat

    for internal, mapping in STATUS_FIELD_MAP.items():
        sid, attr = mapping
        result[internal] = flat.get(f"{sid}.{attr}")

    return result


def find_snapshot_device(
    payload: dict[str, Any], device_id: str
) -> dict[str, Any] | None:
    """Find a device in a snapshot response by thirdPartyDevId."""
    for device in extract_device_list(payload):
        if not isinstance(device, dict):
            continue
        if str(device.get("thirdPartyDevId", "")) == str(device_id):
            return device
    return None


def to_bool(value: Any, default: bool = False) -> bool:
    """Normalize cloud boolean forms (1/0, true/false, on/off, ...) to bool."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "on", "yes", "open"}
    return default


def to_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
