"""Constants for the Fotile integration."""
from __future__ import annotations

from typing import Any, Final

# Import lazily so this module works without Home Assistant (tests, debug tools).
try:  # pragma: no cover
    from homeassistant.const import Platform
except ImportError:  # pragma: no cover
    Platform = None  # type: ignore[assignment]

DOMAIN: Final = "fotile"
MANUFACTURER: Final = "Fotile"

# ---- OAuth 2.0 (Authorization Code + PKCE) ----
OAUTH_AUTHORIZE_URL: Final = "https://api.fotile.com/api/v1/smsOauthHa/index.html"
OAUTH_TOKEN_URL: Final = "https://api.fotile.com/api/oauth/token"

# Public client id; PKCE makes it safe to ship (no client_secret).
OAUTH_CLIENT_ID: Final = "eHyS5pIN8G"
OAUTH_SCOPES: Final[list[str]] = []
PKCE_CODE_VERIFIER_LENGTH: Final = 128

# ---- HA facade (iot-b2b-delegators /ha/v1) ----
# Flat REST only. CorpId, the cloud-cloud envelope (header / namespace) and the
# enterprise-side protocol stay on the server; the client carries no vendor id.
# All endpoints are POST with "Authorization: Bearer <access_token>":
#   /accept-grant
#   /devices
#   /devices/{deviceId}/snapshot
#   /devices/{deviceId}/command
#   /devices/{deviceId}/subscribe
HA_API_BASE_URL: Final = "https://api.fotile.com/open-cloud/ha/v1"

# Only the business codes the client branches on: the facade maps credential
# errors to HTTP 401 and everything else to HTTP 4xx.
CODE_DEVICE_OFFLINE: Final = 10011

# Flat response: code / description plus business fields on the same level.
RESPONSE_KEY_CODE: Final = "code"
KEY_DESCRIPTION: Final = "description"
KEY_DEVICES: Final = "devices"

# Device: id/name at top level, details inside devInfo.
FIELD_MAP_DEVICE_TOP: Final[dict[str, str]] = {
    "device_id": "thirdPartyDevId",
    "name": "devName",
}
FIELD_MAP_DEVICE_INFO: Final[dict[str, str]] = {
    "model": "model",
    "device_type": "devType",
    "manufacturer": "manu",
    "product_id": "prodId",
    "serial_number": "sn",
}

KEY_SERVICES: Final = "services"
KEY_SERVICE_ID: Final = "sid"
KEY_SERVICE_TYPE: Final = "st"
KEY_STATUS: Final = "status"
KEY_DATA: Final = "data"
KEY_TIMESTAMP: Final = "ts"

# Flattened status keys are "{sid}.{attr}".
STATUS_FIELD_MAP: Final[dict[str, tuple[str, str]]] = {
    "power": ("PowerSwitch", "PowerSwitch"),
    "fan_level": ("FanLevel", "FanLevel"),
    "light": ("Light", "Light"),
    # Read-only.
    "left_stove_state": ("LeftStoveState", "LeftStoveState"),
    "right_stove_state": ("RightStoveState", "RightStoveState"),
}

SID_POWER_SWITCH: Final = "PowerSwitch"
SID_FAN_LEVEL: Final = "FanLevel"
SID_LIGHT: Final = "Light"
SID_LEFT_STOVE: Final = "LeftStoveState"
SID_RIGHT_STOVE: Final = "RightStoveState"

# Category is decided by services[].sid; the spec has no devType table.
DEVICE_KIND_RANGE_HOOD: Final = "range_hood"
DEVICE_KIND_STOVE: Final = "stove"
DEVICE_KIND_BY_SID: Final[dict[str, frozenset[str]]] = {
    DEVICE_KIND_RANGE_HOOD: frozenset({SID_POWER_SWITCH, SID_FAN_LEVEL, SID_LIGHT}),
    DEVICE_KIND_STOVE: frozenset({SID_LEFT_STOVE, SID_RIGHT_STOVE}),
}

# FanLevel: 0-standby, 1-low, 2-auto, 3-high.
FAN_LEVEL_STANDBY: Final = 0
FAN_LEVEL_LOW: Final = 1
FAN_LEVEL_AUTO: Final = 2
FAN_LEVEL_HIGH: Final = 3

SWITCH_ON_VALUE: Final = 1
SWITCH_OFF_VALUE: Final = 0

DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 300
DEVICE_LIST_CACHE_TTL: Final = 300
STATUS_STALE_THRESHOLD: Final = 120

CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_THIRD_PARTY_USER_ID: Final = "third_party_user_id"

if Platform is None:  # pragma: no cover
    PLATFORMS: Final[list[Any]] = []
else:
    PLATFORMS: Final[list[Platform]] = [
        Platform.FAN,
        Platform.LIGHT,
        Platform.BINARY_SENSOR,
    ]
