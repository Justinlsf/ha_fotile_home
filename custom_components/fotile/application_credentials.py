"""Application credentials support (user-supplied OAuth client)."""
from __future__ import annotations

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
)

from .const import DOMAIN, OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL
from .core.auth import async_create_implementation


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    return AuthorizationServer(
        authorize_url=OAUTH_AUTHORIZE_URL,
        token_url=OAUTH_TOKEN_URL,
    )


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> AbstractOAuth2Implementation:
    """Return a PKCE-enabled implementation for user-provided credentials."""
    return async_create_implementation(
        hass,
        auth_domain,
        credential.client_id,
        OAUTH_AUTHORIZE_URL,
        OAUTH_TOKEN_URL,
        client_secret=credential.client_secret or "",
    )


async def async_get_description_placeholders(
    hass: HomeAssistant,
) -> dict[str, str]:
    return {
        "console_url": "https://iot.fotile.com/",
        "authorize_url": OAUTH_AUTHORIZE_URL,
        "token_url": OAUTH_TOKEN_URL,
        "domain": DOMAIN,
    }
