"""Shared base for every SEMS EV CONNECT entity."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL, DOMAIN
from .coordinator import SemsCoordinator


class SemsEntity(CoordinatorEntity[SemsCoordinator]):
    """One device, many entities, one poll behind them all."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SemsCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        serial = coordinator.entry.data[CONF_SERIAL]
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=coordinator.entry.title,
            manufacturer="GoodWe",
            serial_number=serial,
        )

    @property
    def _snap(self):
        return self.coordinator.data

    @property
    def available(self) -> bool:
        """Unavailable when the cloud is unreachable, or when it is reachable
        but cannot see the charger - both mean the reading would be a guess."""
        return bool(super().available and self._snap is not None and self._snap.ok)
