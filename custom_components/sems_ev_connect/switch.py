"""Start and stop charging."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SemsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SemsChargingSwitch(hass.data[DOMAIN][entry.entry_id])])


class SemsChargingSwitch(SemsEntity, SwitchEntity):
    _attr_icon = "mdi:ev-station"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "charging", "Charging")

    @property
    def is_on(self) -> bool | None:
        return None if self._snap is None else bool(self._snap.charging)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command("start")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command("stop")
