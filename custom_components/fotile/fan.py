"""Range-hood fan entity (power + FanLevel)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_KIND_RANGE_HOOD,
    FAN_LEVEL_HIGH,
    FAN_LEVEL_LOW,
    FAN_LEVEL_STANDBY,
)
from .coordinator import FotileDataUpdateCoordinator
from .core.mapping import to_bool, to_int
from .entity import FotileEntity

_LOGGER = logging.getLogger(__name__)

# FanLevel(1..3) -> HA percentage. Standby (0) is treated as off.
LEVEL_TO_PERCENTAGE: dict[int, int] = {
    FAN_LEVEL_LOW: 33,
    FAN_LEVEL_AUTO: 67,
    FAN_LEVEL_HIGH: 100,
}
PERCENTAGE_TO_LEVEL: dict[int, int] = {v: k for k, v in LEVEL_TO_PERCENTAGE.items()}


def _nearest_level(percentage: int) -> int:
    if percentage <= 0:
        return FAN_LEVEL_STANDBY
    nearest = min(PERCENTAGE_TO_LEVEL, key=lambda p: abs(p - percentage))
    return PERCENTAGE_TO_LEVEL[nearest]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FotileDataUpdateCoordinator = entry.runtime_data

    entities = [
        FotileRangeHoodFan(coordinator, device)
        for device in coordinator.selected_devices.values()
        if DEVICE_KIND_RANGE_HOOD in device.kinds
    ]
    if entities:
        _LOGGER.debug("Adding %d range hood fan entity(ies)", len(entities))
        async_add_entities(entities)


class FotileRangeHoodFan(FotileEntity, FanEntity):
    """Range-hood fan: power + 3 speed levels (low/auto/high)."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = 3
    _attr_translation_key = "range_hood"

    def __init__(
        self, coordinator: FotileDataUpdateCoordinator, device: Any
    ) -> None:
        super().__init__(coordinator, device, "fan")
        self._attr_name = None

    @property
    def is_on(self) -> bool | None:
        power = self._device.get_status_value("power")
        if power is None:
            return None
        return to_bool(power)

    @property
    def percentage(self) -> int | None:
        level = to_int(self._device.get_status_value("fan_level"))
        if level is None:
            return None
        if level == FAN_LEVEL_STANDBY:
            return 0
        return LEVEL_TO_PERCENTAGE.get(level)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        prod_id = self._device.product_id or None

        if percentage is not None:
            # Always ensure the main power is on before setting a level.
            if not self.is_on:
                await self.async_execute_command(
                    self.coordinator.client.turn_on(self._device.device_id, prod_id)
                )
            level = _nearest_level(percentage)
            if level == FAN_LEVEL_STANDBY:
                level = FAN_LEVEL_LOW
            await self.async_execute_command(
                self.coordinator.client.set_fan_level(
                    self._device.device_id, level, prod_id
                )
            )
        else:
            await self.async_execute_command(
                self.coordinator.client.turn_on(self._device.device_id, prod_id)
            )
            if (self.percentage or 0) == 0:
                await self.async_execute_command(
                    self.coordinator.client.set_fan_level(
                        self._device.device_id, FAN_LEVEL_LOW, prod_id
                    )
                )

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_execute_command(
            self.coordinator.client.turn_off(
                self._device.device_id, self._device.product_id or None
            )
        )
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        prod_id = self._device.product_id or None

        if percentage == 0:
            await self.async_turn_off()
            return

        level = _nearest_level(percentage)
        if level == FAN_LEVEL_STANDBY:
            level = FAN_LEVEL_LOW

        if not self.is_on:
            await self.async_execute_command(
                self.coordinator.client.turn_on(self._device.device_id, prod_id)
            )
        await self.async_execute_command(
            self.coordinator.client.set_fan_level(
                self._device.device_id, level, prod_id
            )
        )
        await self.coordinator.async_request_refresh()
