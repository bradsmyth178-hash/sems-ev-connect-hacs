"""Charge mode.

The options are machine keys - fast / pv_priority / pv_and_battery - and the
words the customer reads come from the translation files on top of them. It has
to be this way round: Home Assistant matches the option literally and rejects
anything else in core, before this module is reached, so offering "Solar +
battery" as the option meant every automation that sent pv_and_battery failed
with a ServiceValidationError. The keys match the community integration the
same blueprints were written for, so one automation drives either.
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_TO_MODE, MODE_KEYS
from .entity import SemsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SemsModeSelect(hass.data[DOMAIN][entry.entry_id])])


class SemsModeSelect(SemsEntity, SelectEntity):
    _attr_icon = "mdi:solar-power-variant"
    _attr_translation_key = "charge_mode"
    _attr_options = list(MODE_KEYS.values())

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "mode", "Charge mode")

    @property
    def current_option(self) -> str | None:
        if self._snap is None:
            return None
        return MODE_KEYS.get(self._snap.mode)

    async def async_select_option(self, option: str) -> None:
        mode = KEY_TO_MODE.get(option)
        if mode is None:
            raise ValueError(f"unknown charge mode: {option}")
        await self.coordinator.async_command("mode", mode)
