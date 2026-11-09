"""Shared type aliases."""
from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import FotileDataUpdateCoordinator

FotileConfigEntry: TypeAlias = ConfigEntry["FotileDataUpdateCoordinator"]

__all__ = ["FotileConfigEntry"]
