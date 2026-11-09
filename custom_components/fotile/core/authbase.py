"""Auth abstraction and minimal implementations (no external deps)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    import aiohttp

__all__ = [
    "AbstractAuth",
    "FotileApiError",
    "FotileAuthError",
    "NoAuth",
    "StaticTokenAuth",
]


class FotileApiError(Exception):
    """Base for all Fotile API errors."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"API error {status_code}: {message}")


class FotileAuthError(FotileApiError):
    """Auth failure that cannot be refreshed automatically."""

    def __init__(
        self, status_code: int, message: str, code: int | None = None
    ) -> None:
        super().__init__(status_code, message)
        self.code = code


class AbstractAuth(ABC):
    """Responsible for returning a currently-valid access_token."""

    @abstractmethod
    async def async_get_access_token(self) -> str:
        ...

    async def async_request(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Send an authenticated request. Default: attach Bearer header."""
        token = await self.async_get_access_token()
        headers = dict(kwargs.pop("headers", None) or {})
        headers["Authorization"] = f"Bearer {token}"
        return await session.request(method, url, **kwargs, headers=headers)


class StaticTokenAuth(AbstractAuth):
    """Fixed token for debug scripts and unit tests (no refresh)."""

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token

    @property
    def access_token(self) -> str:
        return self._access_token

    async def async_get_access_token(self) -> str:
        return self._access_token


class NoAuth(AbstractAuth):
    """Placeholder with no credentials. Any request raises FotileAuthError."""

    async def async_get_access_token(self) -> str:
        raise FotileAuthError(
            401, "No credentials available; authentication pending"
        )
