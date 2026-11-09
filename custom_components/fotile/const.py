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

OAUTH_REDIRECT_URI: Final = "https://my.home-assistant.io/redirect/oauth"
OAUTH_AUTHORIZE_URL: Final = "https://api-test.fotile.com/api/v1/smsOauthHa/index.html"
OAUTH_TOKEN_URL: Final = "https://api-test.fotile.com/api/oauth/token"

# Public client id; PKCE makes it safe to ship (no client_secret).
OAUTH_CLIENT_ID: Final = "eHyS5pIN8G"
OAUTH_SCOPES: Final[list[str]] = []
PKCE_CODE_VERIFIER_LENGTH: Final = 128

API_BASE_URL: Final = "https://api-test.fotile.com/open-cloud"
API_PATH: Final = "/v1/api"

# CorpId issued by Fotile; used for both thirdPartyId and granteeId.
CORP_ID: Final = "db5ad5848cb3805bd5f7bf678ea4a681"

NS_ACCEPT_GRANT: Final = "AcceptGrant"
NS_DEVICE_DISCOVERY: Final = "DeviceDiscovery"
NS_DEVICE_SNAPSHOT: Final = "DeviceSnapshot"
NS_DEVICE_COMMAND: Final = "DeviceCommand"

GRANT_TYPE_OAUTH2_AUTH_CODE: Final = "OAuth2.AuthorizationCode"

# Business errors live in payload.code; HTTP status may stay 200.
CODE_SUCCESS: Final = 0
AUTH_ERROR_CODES: Final[frozenset[int]] = frozenset(
    {10002, 100021, 100022, 10003, 10004, 10008}
)
MISSING_AUTH_CODES: Final[frozenset[int]] = frozenset({10000, 100001})
CODE_DEVICE_NOT_EXIST: Final = 10009
CODE_COMMAND_NOT_SUPPORT: Final = 10010
CODE_DEVICE_OFFLINE: Final = 10011

DEVICE_STATUS_ONLINE: Final = "online"

RESPONSE_KEY_HEADER: Final = "header"
RESPONSE_KEY_PAYLOAD: Final = "payload"
RESPONSE_KEY_CODE: Final = "code"
KEY_DESCRIPTION: Final = "description"
KEY_DEVICES: Final = "devices"
KEY_THIRD_PARTY_DEV_IDS: Final = "thirdPartyDevIds"

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
KEY_COMMAND: Final = "command"

# Category is decided by services[].sid; the spec has no devType table.
DEVICE_KIND_RANGE_HOOD: Final = "range_hood"
DEVICE_KIND_STOVE: Final = "stove"
DEVICE_KIND_BY_SID: Final[dict[str, frozenset[str]]] = {
    DEVICE_KIND_RANGE_HOOD: frozenset({"PowerSwitch", "FanLevel", "Light"}),
    DEVICE_KIND_STOVE: frozenset({"LeftStoveState", "RightStoveState"}),
}

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
CONF_DEVICES_FILTER: Final = "devices_filter"
CONF_THIRD_PARTY_USER_ID: Final = "third_party_user_id"

if Platform is None:  # pragma: no cover
    PLATFORMS: Final[list[Any]] = []
else:
    PLATFORMS: Final[list[Platform]] = [
        Platform.FAN,
        Platform.LIGHT,
        Platform.BINARY_SENSOR,
    ]
