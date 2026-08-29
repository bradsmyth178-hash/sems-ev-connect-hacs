"""Maximum charge power.

Bounded by what the hardware can actually do. A charger cannot charge below its
own floor - asking for less does not charge slower, it fails - and asking for
more than the unit is rated for is silently clamped, so the slider says no
rather than letting someone set something that will not happen.
"""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MIN_CHARGE_KW
from .entity import SemsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SemsPowerLimit(hass.data[DOMAIN][entry.entry_id])])


class SemsPowerLimit(SemsEntity, NumberEntity):
    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_native_min_value = MIN_CHARGE_KW
    _attr_native_step = 0.1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "power_limit", "Maximum charge power")

    @property
    def native_max_value(self) -> float:
        return float(self.coordinator.link.charger_kw or 7)

    @property
    def native_value(self) -> float | None:
        return None if self._snap is None else round(self._snap.max_power_kw, 1)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_command("max_power", value)
