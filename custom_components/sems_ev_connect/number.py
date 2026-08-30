"""Maximum charge power.

Bounded by what the hardware can actually do. A charger cannot charge below its
own floor - asking for less does not charge slower, it fails - and asking for
more than the unit is rated for is silently clamped, so the slider says no
rather than letting someone set something that will not happen.
"""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.number.const import NumberDeviceClass
from homeassistant.const import UnitOfElectricCurrent, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    MIN_CHARGE_CURRENT_A,
    MIN_CHARGE_KW,
    NOMINAL_LINE_VOLTAGE,
)
from .entity import SemsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SemsPowerLimit(coordinator), SemsCurrentLimit(coordinator)])


def current_to_power_kw(current_a: float, charger_kw: float) -> float:
    """Convert EVCC's single-phase ampere limit into the SEMS power contract."""
    current = float(current_a)
    ceiling = float(charger_kw or 7) * 1000 / NOMINAL_LINE_VOLTAGE
    if current < MIN_CHARGE_CURRENT_A or current > ceiling + 0.05:
        raise ValueError(
            f"charging current must be between {MIN_CHARGE_CURRENT_A:g} A "
            f"and {ceiling:.1f} A"
        )
    return round(
        min(float(charger_kw or 7), max(MIN_CHARGE_KW, current * NOMINAL_LINE_VOLTAGE / 1000)),
        1,
    )


def power_to_current_a(power_kw: float) -> float:
    """Represent the charger's confirmed power limit as EVCC amperes."""
    power = float(power_kw or 0)
    if power <= 0:
        return 0.0
    if power <= MIN_CHARGE_KW + 0.05:
        return MIN_CHARGE_CURRENT_A
    return round(power * 1000 / NOMINAL_LINE_VOLTAGE, 1)


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


class SemsCurrentLimit(SemsEntity, NumberEntity):
    """EVCC-compatible maximum current for the single-phase charger."""

    _attr_icon = "mdi:current-ac"
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = MIN_CHARGE_CURRENT_A
    _attr_native_step = 0.1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "current_limit", "Maximum charging current")

    @property
    def native_max_value(self) -> float:
        return round(float(self.coordinator.link.charger_kw or 7) * 1000 / NOMINAL_LINE_VOLTAGE, 1)

    @property
    def native_value(self) -> float | None:
        return None if self._snap is None else power_to_current_a(self._snap.max_power_kw)

    async def async_set_native_value(self, value: float) -> None:
        kw = current_to_power_kw(value, self.coordinator.link.charger_kw)
        await self.coordinator.async_command("max_power", kw)
