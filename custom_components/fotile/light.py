"""Range-hood light entity."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_KIND_RANGE_HOOD, SID_LIGHT
from .coordinator import FotileDataUpdateCoordinator
from .core.mapping import to_bool
from .entity import FotileEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FotileDataUpdateCoordinator = entry.runtime_data

    entities = [
        FotileHoodLight(coordinator, device)
        for device in coordinator.selected_devices.values()
        if DEVICE_KIND_RANGE_HOOD in device.kinds
        and device.supports_service(SID_LIGHT)
    ]
    if entities:
        _LOGGER.debug("Adding %d hood light entity(ies)", len(entities))
        async_add_entities(entities)


class FotileHoodLight(FotileEntity, LightEntity):
    """On/off light for a range hood."""

    _attr_translation_key = "hood_light"
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(
        self, coordinator: FotileDataUpdateCoordinator, device: Any
    ) -> None:
        super().__init__(coordinator, device, "light")
        self._attr_name = None

    @property
    def is_on(self) -> bool | None:
        value = self._device.get_status_value("light")
        if value is None:
            return None
        return to_bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.async_execute_command(
            self.coordinator.client.set_light(
                self._device.device_id, True, self._device.product_id or None
            )
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_execute_command(
            self.coordinator.client.set_light(
                self._device.device_id, False, self._device.product_id or None
            )
        )
        await self.coordinator.async_request_refresh()
