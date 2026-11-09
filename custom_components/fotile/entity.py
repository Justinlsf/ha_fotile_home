"""Base entity for all Fotile platforms."""
from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CODE_COMMAND_NOT_SUPPORT,
    CODE_DEVICE_NOT_EXIST,
    CODE_DEVICE_OFFLINE,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import FotileDataUpdateCoordinator
from .core.api import (
    FotileApiError,
    FotileAuthError,
    FotileBusinessError,
    FotileConnectionError,
)
from .core.device import FotileDevice

# Business error code -> translation key under ``exceptions`` in strings.json.
_BUSINESS_ERROR_KEYS: dict[int, str] = {
    CODE_DEVICE_OFFLINE: "device_offline",
    CODE_DEVICE_NOT_EXIST: "device_not_exist",
    CODE_COMMAND_NOT_SUPPORT: "command_not_supported",
}


class FotileEntity(CoordinatorEntity[FotileDataUpdateCoordinator]):
    """Common base for fan / light / binary_sensor entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FotileDataUpdateCoordinator,
        device: FotileDevice,
        entity_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._entity_key = entity_key
        self._attr_unique_id = f"{device.device_id}_{entity_key}"
        # firmware_version is empty (the spec has no such field); pass None to
        # avoid showing an empty string in the UI.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.model or None,
            sw_version=device.firmware_version or None,
        )

    @property
    def available(self) -> bool:
        """Coordinator ok, device online, and status still fresh."""
        return (
            super().available
            and self._device.online
            and self.coordinator.status_is_fresh(self._device.device_id)
        )

    @property
    def device(self) -> FotileDevice:
        return self._device

    async def async_execute_command(self, command: Awaitable[Any]) -> None:
        """Run a command; translate expected API errors for the UI."""
        try:
            await command
        except FotileAuthError as err:
            # Ask Home Assistant to start the reauth flow.
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                "Fotile authorization expired",
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except FotileBusinessError as err:
            raise HomeAssistantError(
                err.description or "Fotile cloud error",
                translation_domain=DOMAIN,
                translation_key=_BUSINESS_ERROR_KEYS.get(err.code, "command_failed"),
                translation_placeholders={"description": err.description},
            ) from err
        except FotileConnectionError as err:
            raise HomeAssistantError(
                "Unable to reach the Fotile cloud",
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except FotileApiError as err:
            raise HomeAssistantError(
                err.message,
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"description": err.message},
            ) from err
        except ValueError as err:
            raise ServiceValidationError(
                str(err),
                translation_domain=DOMAIN,
                translation_key="invalid_value",
                translation_placeholders={"value": str(err)},
            ) from err
