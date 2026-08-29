"""Read-only charger readings."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CAR_KEYS, DOMAIN, MODE_KEYS
from .entity import SemsEntity
from .models import Snapshot


@dataclass(frozen=True, kw_only=True)
class SemsSensorDescription(SensorEntityDescription):
    value: Callable[[Snapshot], object]


SENSORS: tuple[SemsSensorDescription, ...] = (
    SemsSensorDescription(
        key="status",
        name="Status",
        value=lambda s: s.status_name or None,
    ),
    SemsSensorDescription(
        key="vehicle",
        name="Vehicle state",
        translation_key="vehicle_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(CAR_KEYS.values()),
        value=lambda s: CAR_KEYS.get(s.car),
    ),
    SemsSensorDescription(
        key="charge_mode",
        name="Charge mode",
        translation_key="charge_mode",
        device_class=SensorDeviceClass.ENUM,
        options=list(MODE_KEYS.values()),
        value=lambda s: MODE_KEYS.get(s.mode),
    ),
    SemsSensorDescription(
        key="power",
        name="Charging power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: round(s.power_kw, 2),
    ),
    SemsSensorDescription(
        key="session_energy",
        name="Session energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        # This resets to zero at the next session. ENERGY does not permit the
        # MEASUREMENT state class in Home Assistant, and marking it as TOTAL
        # would incorrectly make it eligible for the Energy dashboard.
        value=lambda s: round(s.session_kwh, 2),
    ),
    SemsSensorDescription(
        key="max_power",
        name="Power limit",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        value=lambda s: round(s.max_power_kw, 1),
    ),
    SemsSensorDescription(
        key="fault",
        name="Fault",
        value=lambda s: ", ".join(s.faults) if s.faults else "None",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SemsSensor(coordinator, d) for d in SENSORS)


class SemsSensor(SemsEntity, SensorEntity):
    entity_description: SemsSensorDescription

    def __init__(self, coordinator, description: SemsSensorDescription) -> None:
        super().__init__(coordinator, description.key, description.name)
        self.entity_description = description

    @property
    def native_value(self):
        if self._snap is None:
            return None
        return self.entity_description.value(self._snap)
