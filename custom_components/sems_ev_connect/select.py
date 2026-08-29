"""Charge mode with stable machine-key options and translated labels."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_KEYS, MODE_KEY_TO_VALUE
from .entity import SemsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SemsModeSelect(hass.data[DOMAIN][entry.entry_id])])


class SemsModeSelect(SemsEntity, SelectEntity):
    _attr_icon = "mdi:solar-power-variant"
    _attr_options = list(MODE_KEYS.values())
    _attr_translation_key = "charge_mode"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "mode", "Charge mode")

    @property
    def current_option(self) -> str | None:
        if self._snap is None:
            return None
        return MODE_KEYS.get(self._snap.mode)

    async def async_select_option(self, option: str) -> None:
        mode = MODE_KEY_TO_VALUE.get(option)
        if mode is None:
            raise ValueError(f"unknown charge mode: {option}")
        await self.coordinator.async_command("mode", mode)
