"""Polling coordinator for a GoodWe charger reached through the SEMS cloud."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FRESH_SNAPSHOT_SECONDS,
    POWER_COMMAND_SPACING,
)
from .models import Snapshot
from .sems import SemsAuthenticationError, SemsLink

_LOGGER = logging.getLogger(__name__)


class SemsCoordinator(DataUpdateCoordinator[Snapshot]):
    """Keeps one charger's readings current.

    Every entity reads from here rather than calling the cloud itself, so a
    page full of entities is still one request per cycle. That matters more
    than usual: SEMS is the same API the owner's phone app uses, and hammering
    it can get their account rate-limited.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, link: SemsLink) -> None:
        self.link = link
        self.entry = entry
        self._snapshot_at = 0.0
        self._pending_power: tuple[float, asyncio.Future[None]] | None = None
        self._power_worker: asyncio.Task[None] | None = None
        self._last_power_write_at = 0.0
        self.power_command_spacing = POWER_COMMAND_SPACING
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> Snapshot:
        try:
            snap = await self.link.snapshot()
        except SemsAuthenticationError as err:
            raise ConfigEntryAuthFailed("SEMS Portal sign-in was not accepted") from err
        except Exception as err:  # noqa: BLE001 - surfaced to HA as unavailable
            raise UpdateFailed(f"could not reach the charger through GoodWe: {err}") from err
        if not snap.ok:
            # A reachable cloud that cannot see the charger is a real state, not
            # an error: the charger is probably powered down or off the network.
            # Keep the entities alive and let them report unavailable readings.
            _LOGGER.debug("charger not reporting: %s", snap.error or "no detail given")
        else:
            self._snapshot_at = time.monotonic()
        return snap

    def _require_fresh_snapshot(self) -> None:
        snap = self.data
        age = time.monotonic() - self._snapshot_at
        if snap is None or not snap.ok or self._snapshot_at <= 0 or age > FRESH_SNAPSHOT_SECONDS:
            raise HomeAssistantError(
                "the charger is unavailable; wait for a fresh status before sending a command"
            )

    async def _run_power_commands(self) -> None:
        """Keep at most one waiting power command and verify each write."""
        try:
            while self._pending_power is not None:
                kw, waiter = self._pending_power
                self._pending_power = None
                try:
                    self._require_fresh_snapshot()
                    delay = self.power_command_spacing - (
                        time.monotonic() - self._last_power_write_at
                    )
                    if delay > 0:
                        await asyncio.sleep(delay)
                    try:
                        await self.link.set_max_power_kw(float(kw), self.link.charger_kw)
                    finally:
                        # Pace attempts as well as successes. A failing cloud must
                        # not turn a waiting EVCC update into an immediate retry loop.
                        self._last_power_write_at = time.monotonic()
                    await self.async_request_refresh()
                except Exception as err:  # noqa: BLE001 - returned to the HA service caller
                    if not waiter.done():
                        waiter.set_exception(err)
                else:
                    if not waiter.done():
                        waiter.set_result(None)
        finally:
            self._power_worker = None

    async def _async_set_max_power(self, kw: float) -> None:
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[None] = loop.create_future()
        if self._pending_power is not None:
            _, superseded = self._pending_power
            if not superseded.done():
                superseded.set_exception(
                    HomeAssistantError("the current request was replaced by a newer value")
                )
        self._pending_power = (float(kw), waiter)
        if self._power_worker is None:
            self._power_worker = loop.create_task(self._run_power_commands())
        await waiter

    async def async_command(self, action: str, value=None) -> None:
        """Send one command, then refresh so the UI reflects what happened.

        The SEMS client verifies its own writes and re-asserts a change the
        charger silently drops, so by the time this returns the charger has
        either taken the command or raised.
        """
        if action == "max_power":
            await self._async_set_max_power(float(value))
            return

        self._require_fresh_snapshot()
        if action == "start":
            await self.link.start_charging()
        elif action == "stop":
            await self.link.stop_charging()
        elif action == "mode":
            await self.link.set_mode(int(value))
        else:
            raise ValueError(f"unknown command: {action}")
        await self.async_request_refresh()


async def build_link(hass: HomeAssistant, username: str, password: str,
                     serial: str, charger_kw: float = 7.0,
                     plant_id: str = "") -> SemsLink:
    """A SEMS client sharing Home Assistant's own HTTP session."""
    return SemsLink(
        username,
        password,
        serial,
        charger_kw=charger_kw,
        phases=1,
        plant_id=plant_id,
        session=async_get_clientsession(hass),
    )
