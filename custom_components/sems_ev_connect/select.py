"""Charge mode.

The options are the words the customer sees everywhere else - Fast, Solar only,
Solar + battery - while the value sent is the raw mode number. Passing display
names to the charger is exactly the mistake that made a set of automations fail
silently, so the mapping lives in one place.
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LABEL_TO_MODE, MODE_LABELS
from .entity import SemsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SemsModeSelect(hass.data[DOMAIN][entry.entry_id])])


class SemsModeSelect(SemsEntity, SelectEntity):
    _attr_icon = "mdi:solar-power-variant"
    _attr_options = list(MODE_LABELS.values())

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "mode", "Charge mode")

    @property
    def current_option(self) -> str | None:
        if self._snap is None:
            return None
        return MODE_LABELS.get(self._snap.mode)

    async def async_select_option(self, option: str) -> None:
        mode = LABEL_TO_MODE.get(option)
        if mode is None:
            raise ValueError(f"unknown charge mode: {option}")
        await self.coordinator.async_command("mode", mode)
