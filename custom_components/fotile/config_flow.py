"""OAuth 2.0 authorization code + PKCE config flow."""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DEVICES_FILTER,
    CONF_SCAN_INTERVAL,
    CONF_THIRD_PARTY_USER_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    OAUTH_AUTHORIZE_URL,
    OAUTH_CLIENT_ID,
    OAUTH_SCOPES,
    OAUTH_TOKEN_URL,
)
from .core.api import FotileApiError, FotileClient, StaticTokenAuth
from .core.auth import async_create_implementation

_LOGGER = logging.getLogger(__name__)


class FotileConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """OAuth 2.0 config flow; only business-specific bits are customized."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        # Fotile's server has no scope concept; omit scope when empty.
        if not OAUTH_SCOPES:
            return {}
        return {"scope": " ".join(OAUTH_SCOPES)}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Register the built-in implementation; on first add the flow runs
        before async_setup, so registering here avoids the credentials prompt."""
        if OAUTH_CLIENT_ID:
            config_entry_oauth2_flow.async_register_implementation(
                self.hass,
                DOMAIN,
                async_create_implementation(
                    self.hass,
                    DOMAIN,
                    OAUTH_CLIENT_ID,
                    OAUTH_AUTHORIZE_URL,
                    OAUTH_TOKEN_URL,
                ),
            )
        return await super().async_step_user(user_input)

    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> ConfigFlowResult:
        unique_id, title, extra_data = await self._async_resolve_identity(data)
        if extra_data:
            data = {**data, **extra_data}

        if self.source == SOURCE_REAUTH:
            # Only update the token; do not touch unique_id (the fallback
            # unique_id is derived from refresh_token, which rotates).
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )

        if unique_id is not None:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

        return self.async_create_entry(title=title, data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def _async_resolve_identity(
        self, data: dict[str, Any]
    ) -> tuple[str | None, str, dict[str, Any]]:
        """Resolve unique_id from AcceptGrant (fallback: refresh-token hash)."""
        token = data.get("token") or {}
        fallback_title = MANUFACTURER

        # Strategy 1: AcceptGrant.
        access_token = token.get("access_token")
        if access_token:
            client = FotileClient(
                StaticTokenAuth(access_token),
                async_get_clientsession(self.hass),
            )
            try:
                third_party_user_id = await client.accept_grant()
            except FotileApiError as err:
                _LOGGER.warning(
                    "Fotile AcceptGrant failed (%s); falling back to "
                    "refresh_token-derived unique_id",
                    err.message,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.warning(
                    "Unexpected error during Fotile AcceptGrant",
                    exc_info=True,
                )
            else:
                if third_party_user_id:
                    return (
                        f"user:{third_party_user_id}",
                        fallback_title,
                        {CONF_THIRD_PARTY_USER_ID: third_party_user_id},
                    )
                _LOGGER.warning(
                    "AcceptGrant returned no thirdPartyUserId; "
                    "falling back to refresh_token-derived unique_id"
                )

        # Strategy 2: SHA-256 of refresh_token (only an irreversible digest is
        # stored). Known limitation: refresh tokens rotate, so re-auth after
        # revocation may create a duplicate entry.
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            _LOGGER.warning(
                "Fotile token response contained no refresh_token. "
                "Home Assistant will be unable to renew access silently."
            )
            return None, fallback_title, {}

        digest = hashlib.sha256(refresh_token.encode()).hexdigest()[:32]
        return f"token:{digest}", fallback_title, {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return FotileOptionsFlow()


class FotileOptionsFlow(OptionsFlow):
    """Options: polling interval and optional device filter."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = getattr(self.config_entry, "runtime_data", None)
        devices = coordinator.devices if coordinator else {}
        device_options = {
            device_id: device.name for device_id, device in devices.items()
        }

        if user_input is not None:
            selected = user_input.get(CONF_DEVICES_FILTER)
            # Store "all devices" as an empty list so devices bound later are
            # included automatically instead of silently filtered out.
            if selected is not None and set(selected) == set(device_options):
                user_input[CONF_DEVICES_FILTER] = []
            return self.async_create_entry(data=user_input)

        schema: dict[Any, Any] = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
            ),
        }

        if device_options:
            selected = self.config_entry.options.get(CONF_DEVICES_FILTER)
            if not selected:
                # Empty / unset means all devices.
                selected = list(device_options)
            else:
                selected = [
                    device_id
                    for device_id in selected
                    if device_id in device_options
                ]
            schema[vol.Optional(CONF_DEVICES_FILTER, default=selected)] = (
                cv.multi_select(device_options)
            )

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
