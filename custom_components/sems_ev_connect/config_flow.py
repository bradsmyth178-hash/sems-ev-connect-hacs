"""Setup flow: sign in with GoodWe, then pick the charger.

Deliberately does not ask for a serial number. Reading one off a unit mounted in
a garage is the fiddliest part of setting this up, and mistyping it fails in a
way that looks like a broken connection rather than a typo. The account already
knows which chargers it has, so it is asked instead.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PLANT_ID, CONF_SERIAL, DOMAIN
from .sems import SemsAuthenticationError, SemsLink

_LOGGER = logging.getLogger(__name__)

CREDENTIALS_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class SemsEvConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Two steps at most, and only one of them if the account has one charger."""

    VERSION = 1

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._chargers: list[dict[str, str]] = []
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME].strip()
            self._password = user_input[CONF_PASSWORD]
            link = SemsLink(
                self._username,
                self._password,
                "unknown",
                session=async_get_clientsession(self.hass),
            )
            try:
                probe = await link.account_probe()
            except SemsAuthenticationError as err:
                # Sign-in failed and "no charger on the account" are different
                # problems with different fixes, so they get different errors.
                _LOGGER.debug("GoodWe sign-in failed: %s", err)
                errors["base"] = "invalid_auth"
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("SEMS Portal could not be reached: %s", err)
                errors["base"] = "cannot_connect"
            else:
                self._chargers = probe.get("chargers") or []
                if not self._chargers:
                    errors["base"] = "no_chargers"

            if not errors:
                if len(self._chargers) == 1:
                    return await self._create_async(self._chargers[0])
                return await self.async_step_charger()

        return self.async_show_form(
            step_id="user", data_schema=CREDENTIALS_SCHEMA, errors=errors
        )

    async def async_step_charger(
        self, user_input: dict[str, Any] | None = None
    ):
        """Only reached when the account holds more than one charger."""
        if user_input is not None:
            chosen = next(
                (c for c in self._chargers if c["serial"] == user_input[CONF_SERIAL]),
                None,
            )
            if chosen:
                return await self._create_async(chosen)

        options = {
            c["serial"]: " - ".join(p for p in (c.get("name"), c["serial"]) if p)
            for c in self._chargers
        }
        return self.async_show_form(
            step_id="charger",
            data_schema=vol.Schema({vol.Required(CONF_SERIAL): vol.In(options)}),
        )

    async def _create_async(self, charger: dict[str, str]):
        serial = charger["serial"]
        # One entry per charger, so adding the same one twice is refused rather
        # than silently creating a second set of entities for it.
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=charger.get("name") or f"Charger {serial}",
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_SERIAL: serial,
                CONF_PLANT_ID: charger.get("plant_id") or "",
            },
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Offered when the stored password stops being accepted."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ):
        """Check a replacement password and update the existing entry."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry
        if entry is None:
            return self.async_abort(reason="reauth_entry_missing")

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            link = SemsLink(
                entry.data[CONF_USERNAME],
                password,
                entry.data[CONF_SERIAL],
                plant_id=entry.data.get(CONF_PLANT_ID, ""),
                session=async_get_clientsession(self.hass),
            )
            try:
                await link.account_probe()
            except SemsAuthenticationError as err:
                _LOGGER.debug("SEMS reauthentication was rejected: %s", err)
                errors["base"] = "invalid_auth"
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("SEMS Portal could not be reached during reauthentication: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
        )
