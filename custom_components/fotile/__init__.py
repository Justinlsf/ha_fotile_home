"""Fotile integration setup."""
from __future__ import annotations

import logging
from typing import Final

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_THIRD_PARTY_USER_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OAUTH_AUTHORIZE_URL,
    OAUTH_CLIENT_ID,
    OAUTH_TOKEN_URL,
    PLATFORMS,
)
from .coordinator import FotileDataUpdateCoordinator
from .core.api import FotileAuthError, FotileClient, FotileConnectionError
from .core.auth import OAuth2SessionAuth, async_create_implementation
from .types import FotileConfigEntry

_LOGGER = logging.getLogger(__name__)

__all__: Final[list[str]] = [
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the built-in OAuth client when a client id is configured."""
    if not OAUTH_CLIENT_ID:
        _LOGGER.warning(
            "Fotile built-in OAuth client_id is not configured; "
            "users must provide their own credentials via "
            "Settings -> Devices & Services -> Application credentials."
        )
        return True

    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        async_create_implementation(
            hass,
            DOMAIN,
            OAUTH_CLIENT_ID,
            OAUTH_AUTHORIZE_URL,
            OAUTH_TOKEN_URL,
        ),
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: FotileConfigEntry
) -> bool:
    """Set up the integration for a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    oauth_session = config_entry_oauth2_flow.OAuth2Session(
        hass, entry, implementation
    )
    auth = OAuth2SessionAuth(oauth_session)

    client = FotileClient(auth, async_get_clientsession(hass))

    # Restore persisted user id to skip re-running AcceptGrant on every reload.
    stored_user_id = entry.data.get(CONF_THIRD_PARTY_USER_ID)
    if stored_user_id:
        client.set_third_party_user_id(str(stored_user_id))

    # AcceptGrant is required by every device namespace (idempotent).
    try:
        third_party_user_id = await client.accept_grant()
    except FotileAuthError as err:
        raise ConfigEntryAuthFailed(
            f"Fotile AcceptGrant failed: {err.message}"
        ) from err
    except FotileConnectionError as err:
        raise ConfigEntryNotReady(
            f"Fotile AcceptGrant connection error: {err.message}"
        ) from err

    if third_party_user_id and third_party_user_id != stored_user_id:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_THIRD_PARTY_USER_ID: third_party_user_id},
        )

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    coordinator = FotileDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        scan_interval=scan_interval,
    )

    # First refresh before platform setup so token problems surface now.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload the integration when the device set changes (bind/unbind in app),
    # since platforms only create entities at setup time.
    known_device_ids = frozenset(coordinator.devices)

    @callback
    def _async_reload_on_device_change() -> None:
        nonlocal known_device_ids
        current_device_ids = frozenset(coordinator.devices)
        if current_device_ids == known_device_ids:
            return
        previous_count = len(known_device_ids)
        known_device_ids = current_device_ids
        _LOGGER.info(
            "Fotile device list changed (%d -> %d device(s)), reloading integration",
            previous_count,
            len(current_device_ids),
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        coordinator.async_add_listener(_async_reload_on_device_change)
    )

    # Reload on options change (scan interval). Token refresh also fires the
    # update listener but only writes entry.data, so compare options only to
    # avoid reloading on every token refresh.
    last_options = dict(entry.options)

    async def _async_options_updated(
        _hass: HomeAssistant, _entry: FotileConfigEntry
    ) -> None:
        nonlocal last_options
        if dict(_entry.options) == last_options:
            return
        last_options = dict(_entry.options)
        await _hass.config_entries.async_reload(_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    _LOGGER.info(
        "Fotile integration set up successfully; %d device(s) discovered.",
        len(coordinator.devices),
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FotileConfigEntry
) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = entry.runtime_data
        await coordinator.client.close()

    return unload_ok
