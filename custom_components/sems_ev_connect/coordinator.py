"""Polling coordinator for a GoodWe charger reached through the SEMS cloud."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import Snapshot
from .sems import SemsLink

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
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> Snapshot:
        try:
            snap = await self.link.snapshot()
        except Exception as err:  # noqa: BLE001 - surfaced to HA as unavailable
            raise UpdateFailed(f"could not reach the charger through GoodWe: {err}") from err
        if not snap.ok:
            # A reachable cloud that cannot see the charger is a real state, not
            # an error: the charger is probably powered down or off the network.
            # Keep the entities alive and let them report unavailable readings.
            _LOGGER.debug("charger not reporting: %s", snap.error or "no detail given")
        return snap

    async def async_command(self, action: str, value=None) -> None:
        """Send one command, then refresh so the UI reflects what happened.

        The SEMS client verifies its own writes and re-asserts a change the
        charger silently drops, so by the time this returns the charger has
        either taken the command or raised.
        """
        if action == "start":
            await self.link.start_charging()
        elif action == "stop":
            await self.link.stop_charging()
        elif action == "mode":
            await self.link.set_mode(int(value))
        elif action == "max_power":
            await self.link.set_max_power_kw(float(value), self.link.charger_kw)
        else:
            raise ValueError(f"unknown command: {action}")
        await self.async_request_refresh()


async def build_link(hass: HomeAssistant, username: str, password: str,
                     serial: str, charger_kw: float = 7.0) -> SemsLink:
    """A SEMS client sharing Home Assistant's own HTTP session."""
    return SemsLink(
        username,
        password,
        serial,
        charger_kw=charger_kw,
        phases=1,
        session=async_get_clientsession(hass),
    )
