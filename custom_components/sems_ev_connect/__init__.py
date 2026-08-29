"""SEMS EV CONNECT - a GoodWe HCA charger in Home Assistant.

The first-generation HCA charger has no local control protocol: no Modbus, no
LAN API, no OCPP of its own. It is reachable only through GoodWe's SEMS cloud,
which is why this integration signs in with the owner's own GoodWe account
rather than talking to anything on the home network.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_PLANT_ID, CONF_SERIAL, DOMAIN
from .coordinator import SemsCoordinator, build_link

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    link = await build_link(
        hass,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_SERIAL],
        plant_id=entry.data.get(CONF_PLANT_ID, ""),
    )
    coordinator = SemsCoordinator(hass, entry, link)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        raise
    except ConfigEntryNotReady:
        raise
    except Exception as err:  # noqa: BLE001
        message = str(err).lower()
        # A rejected sign-in is the owner's problem to fix and must prompt them,
        # rather than retrying forever against an account that will keep saying
        # no - repeated failures are how a GoodWe account gets locked.
        if "sign-in" in message or "password" in message or "not accepted" in message:
            raise ConfigEntryAuthFailed(str(err)) from err
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: SemsCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.link.close()
    return unloaded
