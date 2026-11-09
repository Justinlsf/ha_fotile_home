"""OAuth 2.0 authorization code + PKCE helpers."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from ..const import PKCE_CODE_VERIFIER_LENGTH
from .authbase import AbstractAuth, FotileAuthError
from .pkce import compute_code_challenge, generate_code_verifier

_LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover
    from homeassistant.helpers.config_entry_oauth2_flow import (
        LocalOAuth2ImplementationWithPkce as _BuiltinPkceImplementation,
    )

    HAS_BUILTIN_PKCE = True
except ImportError:  # pragma: no cover
    _BuiltinPkceImplementation = None
    HAS_BUILTIN_PKCE = False

try:  # pragma: no cover
    from homeassistant.helpers.config_entry_oauth2_flow import (
        OAuth2TokenRequestReauthError as _OAuth2ReauthError,
    )
except ImportError:  # pragma: no cover
    _OAuth2ReauthError = None  # type: ignore[assignment,misc]


class FotilePkceImplementation(
    config_entry_oauth2_flow.LocalOAuth2Implementation
):
    """PKCE-enabled OAuth implementation (fallback for older HA)."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        authorize_url: str,
        token_url: str,
        client_secret: str = "",
        code_verifier_length: int = PKCE_CODE_VERIFIER_LENGTH,
    ) -> None:
        super().__init__(
            hass,
            domain,
            client_id,
            client_secret,
            authorize_url,
            token_url,
        )
        self.code_verifier = generate_code_verifier(code_verifier_length)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        return {
            "code_challenge": compute_code_challenge(self.code_verifier),
            "code_challenge_method": "S256",
        }

    async def _token_request(self, data: dict[str, Any]) -> dict[str, Any]:
        # verifier only matters for authorization_code, not refresh_token.
        if data.get("grant_type") == "authorization_code":
            data = {**data, "code_verifier": self.code_verifier}
        return await super()._token_request(data)


def async_create_implementation(
    hass: HomeAssistant,
    domain: str,
    client_id: str,
    authorize_url: str,
    token_url: str,
    client_secret: str = "",
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Create a PKCE-enabled implementation (prefer built-in)."""
    if _BuiltinPkceImplementation is not None:
        _LOGGER.debug("Using Home Assistant's built-in PKCE implementation")
        return _BuiltinPkceImplementation(
            hass,
            domain,
            client_id,
            authorize_url=authorize_url,
            token_url=token_url,
            client_secret=client_secret,
            code_verifier_length=PKCE_CODE_VERIFIER_LENGTH,
        )

    _LOGGER.debug("Using bundled PKCE fallback implementation")
    return FotilePkceImplementation(
        hass,
        domain,
        client_id,
        authorize_url,
        token_url,
        client_secret=client_secret,
        code_verifier_length=PKCE_CODE_VERIFIER_LENGTH,
    )


class OAuth2SessionAuth(AbstractAuth):
    """Adapt HA's OAuth2Session to AbstractAuth."""

    def __init__(
        self,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        self._oauth_session = oauth_session

    @property
    def oauth_session(self) -> config_entry_oauth2_flow.OAuth2Session:
        return self._oauth_session

    async def async_get_access_token(self) -> str:
        try:
            await self._oauth_session.async_ensure_token_valid()
        except Exception as err:  # noqa: BLE001
            auth_error = _translate_reauth_error(err)
            if auth_error is not None:
                raise auth_error from err
            raise

        token = self._oauth_session.token or {}
        access_token = token.get("access_token")
        if not access_token:
            raise FotileAuthError(401, "OAuth token response missing access_token")
        return str(access_token)

    async def async_request(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        # session is ignored: OAuth2Session uses HA's shared session.
        try:
            return await self._oauth_session.async_request(method, url, **kwargs)
        except Exception as err:  # noqa: BLE001
            auth_error = _translate_reauth_error(err)
            if auth_error is not None:
                raise auth_error from err
            raise


def _translate_reauth_error(err: BaseException) -> FotileAuthError | None:
    """Map HA's reauth error to FotileAuthError."""
    if _OAuth2ReauthError is not None and isinstance(err, _OAuth2ReauthError):
        return FotileAuthError(
            401, f"OAuth refresh token rejected, re-authentication required: {err}"
        )
    return None
