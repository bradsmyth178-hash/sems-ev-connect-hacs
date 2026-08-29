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

from .const import CAR_LABELS, DOMAIN, MODE_LABELS
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
        name="Vehicle",
        # Plain words rather than the raw code, because this is the one an
        # automation condition is most often written against by hand.
        value=lambda s: CAR_LABELS.get(s.car, "Unknown"),
    ),
    SemsSensorDescription(
        key="charge_mode",
        name="Charge mode",
        value=lambda s: MODE_LABELS.get(s.mode, s.mode_name or None),
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
        # This resets to zero when a new session starts, so it is not TOTAL and
        # must not be fed to the energy dashboard as one.
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: round(s.session_kwh, 2),
    ),
    SemsSensorDescription(
        key="lifetime_energy",
        name="Total energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=lambda s: round(s.lifetime_kwh, 2),
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
