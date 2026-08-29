"""Tests for the SEMS EV CONNECT Home Assistant integration.

Run: python -m tests.test_integration   (from the repository root)

These need Home Assistant installed, because half the point is proving the
integration still loads against a real one. Everything else runs offline: no
network, no GoodWe account, no charger. What cannot be proven here is behaviour
against real hardware, and nothing in this file pretends otherwise.

The charge-mode test is the one that matters most. Home Assistant validates a
select option before the integration handler is called, so automations must use
stable machine keys while the UI translates those keys into friendly labels.
The mapping is pinned all the way from service input to the raw SEMS number.
"""
from __future__ import annotations

import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASSED: list[str] = []


def ok(msg: str) -> None:
    PASSED.append(msg)
    print(f"PASS {msg}")


# ---------------------------------------------------------------- imports
def check_every_module_imports() -> None:
    """A module that fails to import is an integration that does not appear."""
    mods = ["const", "models", "registers", "sems", "coordinator", "entity",
            "config_flow", "sensor", "switch", "select", "number"]
    for m in mods:
        importlib.import_module(f"custom_components.sems_ev_connect.{m}")
    importlib.import_module("custom_components.sems_ev_connect")
    import homeassistant.const as hac
    ok(f"all {len(mods) + 1} modules import against Home Assistant {hac.__version__}")


# ---------------------------------------------------------------- manifest
def check_manifest() -> None:
    p = os.path.join(ROOT, "custom_components", "sems_ev_connect", "manifest.json")
    m = json.load(open(p, encoding="utf-8"))
    for key in ("domain", "name", "version", "documentation", "issue_tracker", "codeowners"):
        assert m.get(key), f"manifest is missing {key} - HACS requires it"
    assert m["config_flow"] is True, "the integration must be addable from the UI"
    from custom_components.sems_ev_connect.const import DOMAIN
    assert m["domain"] == DOMAIN, "manifest domain and const DOMAIN disagree"
    folder = os.path.basename(os.path.dirname(p))
    assert folder == m["domain"], "the folder name must equal the domain, or HA will not load it"
    hacs = json.load(open(os.path.join(ROOT, "hacs.json"), encoding="utf-8"))
    assert hacs.get("name"), "hacs.json needs a name"
    ok(f"manifest and hacs.json are valid ({m['name']} v{m['version']})")


# ---------------------------------------------------------------- charge modes
def check_mode_round_trip() -> None:
    from custom_components.sems_ev_connect.const import (
        MODE_FAST, MODE_KEYS, MODE_KEY_TO_VALUE, MODE_SOLAR_BATTERY,
        MODE_SOLAR_ONLY,
    )

    expected = {
        MODE_FAST: "fast",
        MODE_SOLAR_ONLY: "pv_priority",
        MODE_SOLAR_BATTERY: "pv_and_battery",
    }
    assert MODE_KEYS == expected

    # Every Home Assistant state key maps to a raw SEMS number and back.
    for mode, key in MODE_KEYS.items():
        assert isinstance(mode, int), f"{key} must map to a number, not {mode!r}"
        assert MODE_KEY_TO_VALUE[key] == mode, f"{key} does not round-trip"

    # Home Assistant validates against this list *before* async_select_option.
    from custom_components.sems_ev_connect.select import SemsModeSelect
    inst = SemsModeSelect.__new__(SemsModeSelect)
    assert inst.options == ["fast", "pv_priority", "pv_and_battery"], inst.options

    for relative in (
        ("custom_components", "sems_ev_connect", "strings.json"),
        ("custom_components", "sems_ev_connect", "translations", "en.json"),
    ):
        translation = json.load(open(os.path.join(ROOT, *relative), encoding="utf-8"))
        labels = translation["entity"]["select"]["charge_mode"]["state"]
        assert labels == {
            "fast": "Fast",
            "pv_priority": "Solar only",
            "pv_and_battery": "Solar + battery",
        }
        vehicle_labels = translation["entity"]["sensor"]["vehicle_state"]["state"]
        assert vehicle_labels == {
            "not_plugged_in": "Not plugged in",
            "half_connected": "Half connected",
            "connected": "Connected",
        }
    ok("charge modes round-trip: machine keys accepted, translated labels shown, numbers sent")


def check_select_service_contract() -> None:
    """Exercise the validation order used by Home Assistant select services."""
    import asyncio

    from homeassistant.exceptions import ServiceValidationError
    from custom_components.sems_ev_connect.select import SemsModeSelect

    class Coordinator:
        calls: list[tuple[str, int]] = []

        async def async_command(self, action: str, value: int) -> None:
            self.calls.append((action, value))

    sel = SemsModeSelect.__new__(SemsModeSelect)
    sel.coordinator = Coordinator()

    # This is the exact machine key shipped in Ron's automations. It must pass
    # Home Assistant's own pre-handler validation, then send SEMS mode 1.
    sel._valid_option_or_raise("pv_priority")
    asyncio.run(SemsModeSelect.async_select_option(sel, "pv_priority"))
    assert sel.coordinator.calls == [("mode", 1)]

    # A translated display label is not a service value. Prove Home Assistant
    # rejects it before the integration handler can run.
    try:
        sel._valid_option_or_raise("Solar only")
    except ServiceValidationError:
        pass
    else:
        raise AssertionError("Home Assistant accepted a translated label as a service value")

    try:
        asyncio.run(SemsModeSelect.async_select_option(sel, "not_a_mode"))
    except ValueError:
        pass
    else:
        raise AssertionError("the handler accepted an unknown machine key")
    ok("Home Assistant accepts Ron's mode keys and the handler sends the matching SEMS number")


# ---------------------------------------------------------------- entities
def check_sensor_values() -> None:
    from homeassistant.components.sensor import SensorDeviceClass
    from custom_components.sems_ev_connect.models import Snapshot
    from custom_components.sems_ev_connect.sensor import SENSORS

    live = Snapshot(ok=True, status=3, status_name="Charging", car=2, power_kw=6.8123,
                    session_kwh=12.3456, lifetime_kwh=980.5, max_power_kw=7.0,
                    mode=1, mode_name="PV priority", faults=[])
    values = {d.key: d.value(live) for d in SENSORS}

    assert values["status"] == "Charging"
    assert values["vehicle"] == "connected"
    assert values["charge_mode"] == "pv_priority", values["charge_mode"]
    assert values["power"] == 6.81, "power should be rounded, not raw float noise"
    assert values["session_energy"] == 12.35
    assert values["fault"] == "None"

    unplugged = Snapshot(ok=True, car=0)
    vehicle = next(d for d in SENSORS if d.key == "vehicle")
    assert vehicle.value(unplugged) == "not_plugged_in"
    assert vehicle.name == "Vehicle state"
    assert vehicle.device_class is SensorDeviceClass.ENUM
    assert vehicle.options == ["not_plugged_in", "half_connected", "connected"]

    mode = next(d for d in SENSORS if d.key == "charge_mode")
    assert mode.device_class is SensorDeviceClass.ENUM
    assert mode.options == ["fast", "pv_priority", "pv_and_battery"]

    # This is the exact gate used by the supplied blueprints. With no car,
    # the start branch must be false; connected states must remain eligible.
    no_car_states = {
        "not_plugged_in", "disconnected", "unplugged", "not_connected",
        "off", "false", "no", "0", "none", "unavailable", "offline",
    }
    should_start = vehicle.value(unplugged).lower() not in no_car_states
    assert should_start is False
    assert vehicle.value(Snapshot(ok=True, car=2)).lower() not in no_car_states
    ok("sensor states and enum options match the supplied automation safety gate")


def check_sensor_state_classes_are_valid() -> None:
    """Invalid device/state-class pairs are rejected by Home Assistant."""
    from homeassistant.components.sensor import DEVICE_CLASS_STATE_CLASSES
    from custom_components.sems_ev_connect.sensor import SENSORS

    for description in SENSORS:
        if description.device_class is None or description.state_class is None:
            continue
        allowed = DEVICE_CLASS_STATE_CLASSES.get(description.device_class)
        assert allowed is None or description.state_class in allowed, (
            f"{description.key}: {description.device_class} does not allow "
            f"{description.state_class}"
        )
    ok("every sensor device/state-class pairing is valid in Home Assistant")


def check_sensors_survive_an_empty_snapshot() -> None:
    """A charger that has not reported must not raise on a dashboard."""
    from custom_components.sems_ev_connect.models import Snapshot
    from custom_components.sems_ev_connect.sensor import SENSORS

    blank = Snapshot()
    for d in SENSORS:
        d.value(blank)   # must not raise

    # A fault list that arrives as something odd must not take the page down.
    for junk in ([], ["E12"], ["E12", "E31"]):
        out = [d for d in SENSORS if d.key == "fault"][0].value(Snapshot(ok=True, faults=junk))
        assert isinstance(out, str)
    ok("no sensor raises on an empty snapshot or an odd fault list")


def check_power_limit_bounds() -> None:
    """A charger cannot charge below its floor; asking for less fails rather
    than charging slowly, so the slider must not offer it."""
    from custom_components.sems_ev_connect.const import MIN_CHARGE_KW
    from custom_components.sems_ev_connect.number import SemsPowerLimit

    class Link:
        charger_kw = 7

    class Coord:
        link = Link()

    # Read off an instance: NumberEntity exposes these through properties, so
    # the class attribute is not what Home Assistant actually uses.
    n = SemsPowerLimit.__new__(SemsPowerLimit)
    n.coordinator = Coord()
    assert n.native_min_value == MIN_CHARGE_KW == 1.4, n.native_min_value
    assert n.native_step == 0.1, n.native_step
    assert n.native_max_value == 7.0, "the ceiling must come from the charger, not a constant"
    ok("the power limit is bounded by what the charger can actually do")


def check_entities_are_uniquely_identified() -> None:
    """Two entities sharing a unique id silently collapse into one."""
    from custom_components.sems_ev_connect.sensor import SENSORS
    keys = [d.key for d in SENSORS]
    assert len(keys) == len(set(keys)), f"duplicate sensor keys: {keys}"
    ok(f"all {len(keys)} sensor keys are distinct")


# ---------------------------------------------------------------- config flow
def check_config_flow_error_paths() -> None:
    """Sign-in failure and no-charger are different problems with different
    fixes, so they must not share a message."""
    import asyncio

    from custom_components.sems_ev_connect.config_flow import SemsEvConnectConfigFlow

    flow = SemsEvConnectConfigFlow()
    shown: dict = {}

    def fake_show(step_id, data_schema=None, errors=None):
        shown.update(step=step_id, schema=data_schema, errors=errors or {})
        return {"type": "form", "step_id": step_id, "errors": errors or {}}

    flow.async_show_form = fake_show
    flow.hass = object()

    class Refuses:
        async def account_probe(self):
            from custom_components.sems_ev_connect.sems import SemsAuthenticationError
            raise SemsAuthenticationError("SEMS sign-in was not accepted")

    class Offline:
        async def account_probe(self):
            raise ConnectionError("network unavailable")

    class NoChargers:
        async def account_probe(self):
            return {"signed_in": True, "chargers": [], "plants": ["Home"]}

    import custom_components.sems_ev_connect.config_flow as cf
    real_link, real_session = cf.SemsLink, cf.async_get_clientsession
    cf.async_get_clientsession = lambda hass: None
    try:
        cf.SemsLink = lambda *a, **k: Refuses()
        asyncio.run(flow.async_step_user({"username": "a@b.com", "password": "x"}))
        assert shown["errors"].get("base") == "invalid_auth", shown

        cf.SemsLink = lambda *a, **k: Offline()
        asyncio.run(flow.async_step_user({"username": "a@b.com", "password": "x"}))
        assert shown["errors"].get("base") == "cannot_connect", shown

        cf.SemsLink = lambda *a, **k: NoChargers()
        asyncio.run(flow.async_step_user({"username": "a@b.com", "password": "x"}))
        assert shown["errors"].get("base") == "no_chargers", shown
    finally:
        cf.SemsLink, cf.async_get_clientsession = real_link, real_session

    # An empty form must not error before anything has been entered.
    shown.clear()
    asyncio.run(flow.async_step_user(None))
    assert shown["errors"] == {}, shown

    # Model/generation identifiers may be retained internally by SEMS, but the
    # customer chooses a named charger and serial only.
    flow._chargers = [{
        "serial": "CHARGER-A", "name": "Garage", "model": "GW7K-HCA-G2",
        "plant_id": "plant-a",
    }]
    shown.clear()
    asyncio.run(flow.async_step_charger(None))
    validator = next(iter(shown["schema"].schema.values()))
    assert validator.container == {"CHARGER-A": "Garage - CHARGER-A"}
    assert "GW7K-HCA-G2" not in str(validator.container)
    ok("setup distinguishes failures and hides model or generation choices")


def check_auth_failure_starts_reauthentication() -> None:
    """Rejected credentials must not become a permanently unavailable device."""
    import asyncio

    from homeassistant.exceptions import ConfigEntryAuthFailed
    from custom_components.sems_ev_connect.coordinator import SemsCoordinator
    from custom_components.sems_ev_connect.sems import SemsAuthenticationError, SemsLink

    link = SemsLink("owner@example.com", "expired", "CHARGER-A")

    async def rejected_data():
        raise SemsAuthenticationError("SEMS session was not accepted")

    link.data = rejected_data
    try:
        asyncio.run(link.snapshot())
    except SemsAuthenticationError:
        pass
    else:
        raise AssertionError("snapshot swallowed a SEMS authentication failure")

    # A successful login followed by a failed discovery call must retain the
    # real cause. Otherwise setup reports "no charger" for an expired session
    # or an unavailable cloud endpoint.
    async def token_ok(*args, **kwargs):
        return None

    async def rejected_probe(*args, **kwargs):
        raise SemsAuthenticationError("SEMS session was not accepted")

    link._ensure_token = token_ok
    link._post = rejected_probe
    try:
        asyncio.run(link.account_probe())
    except SemsAuthenticationError:
        pass
    else:
        raise AssertionError("account discovery downgraded an authentication failure")

    async def offline_probe(*args, **kwargs):
        raise ConnectionError("SEMS unavailable")

    link._post = offline_probe
    try:
        asyncio.run(link.account_probe())
    except ConnectionError:
        pass
    else:
        raise AssertionError("account discovery downgraded a connection failure")

    class RejectedLink:
        async def snapshot(self):
            raise SemsAuthenticationError("SEMS session was not accepted")

    coordinator = SemsCoordinator.__new__(SemsCoordinator)
    coordinator.link = RejectedLink()
    try:
        asyncio.run(SemsCoordinator._async_update_data(coordinator))
    except ConfigEntryAuthFailed:
        pass
    else:
        raise AssertionError("the coordinator did not ask Home Assistant to reauthenticate")

    # The reauthentication form updates the existing entry instead of entering
    # the normal setup flow and aborting as 'already configured'.
    from types import SimpleNamespace
    from custom_components.sems_ev_connect.config_flow import SemsEvConnectConfigFlow
    from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
    from custom_components.sems_ev_connect.const import CONF_PLANT_ID, CONF_SERIAL

    flow = SemsEvConnectConfigFlow()
    entry = SimpleNamespace(data={
        CONF_USERNAME: "owner@example.com",
        CONF_PASSWORD: "expired",
        CONF_SERIAL: "CHARGER-A",
        CONF_PLANT_ID: "plant-a",
    })
    flow._reauth_entry = entry
    captured: dict = {}

    class Accepts:
        async def account_probe(self):
            return {"signed_in": True}

    import custom_components.sems_ev_connect.config_flow as config_flow_module
    real_link = config_flow_module.SemsLink
    real_session = config_flow_module.async_get_clientsession
    config_flow_module.SemsLink = lambda *args, **kwargs: Accepts()
    config_flow_module.async_get_clientsession = lambda hass: None
    flow.hass = object()
    flow.async_update_reload_and_abort = (
        lambda existing, **kwargs: captured.update(entry=existing, **kwargs) or kwargs
    )
    try:
        asyncio.run(flow.async_step_reauth_confirm({CONF_PASSWORD: "current"}))
    finally:
        config_flow_module.SemsLink = real_link
        config_flow_module.async_get_clientsession = real_session

    assert captured["entry"] is entry
    assert captured["data"][CONF_PASSWORD] == "current"
    assert captured["data"][CONF_SERIAL] == "CHARGER-A"
    ok("rejected credentials trigger Home Assistant reauth and replace only the password")


def check_multi_plant_charger_routing() -> None:
    """The chosen charger must retain its own plant id or writes fail later."""
    import asyncio

    from custom_components.sems_ev_connect.sems import (
        PATH_DEVICE_PAGE,
        PATH_STATIONS_PAGE,
        SemsLink,
    )

    link = SemsLink("owner@example.com", "password", "CHARGER-B")

    async def fake_post(path: str, body: dict, **kwargs):
        if path == PATH_DEVICE_PAGE:
            return {
                "data": {
                    "dataList": [
                        {
                            "stationId": "plant-a",
                            "children": [{"sn": "CHARGER-A", "name": "Garage A"}],
                        },
                        {
                            "stationId": "plant-b",
                            "children": [{"sn": "CHARGER-B", "name": "Garage B"}],
                        },
                    ]
                }
            }
        if path == PATH_STATIONS_PAGE:
            return {"data": {"dataList": [
                {"stationId": "plant-a"}, {"stationId": "plant-b"}
            ]}}
        raise AssertionError(f"unexpected SEMS path: {path}")

    link._post = fake_post
    chargers = asyncio.run(link.list_chargers())
    assert [(c["serial"], c["plant_id"]) for c in chargers] == [
        ("CHARGER-A", "plant-a"),
        ("CHARGER-B", "plant-b"),
    ]
    assert asyncio.run(link._ensure_plant_id(required=True)) == "plant-b"
    payload = asyncio.run(link._command_payload())
    assert payload["plantId"] == "plant-b"

    # The setup entry and startup constructor both have to carry that id. A
    # discovery-only fix would let setup pass and still make commands fail.
    from custom_components.sems_ev_connect.config_flow import SemsEvConnectConfigFlow
    from custom_components.sems_ev_connect.const import CONF_PLANT_ID

    flow = SemsEvConnectConfigFlow()
    flow._username = "owner@example.com"
    flow._password = "password"
    created: dict = {}

    async def fake_set_unique_id(value):
        created["unique_id"] = value

    flow.async_set_unique_id = fake_set_unique_id
    flow._abort_if_unique_id_configured = lambda: None
    flow.async_create_entry = lambda **kwargs: created.update(kwargs) or kwargs
    asyncio.run(flow._create_async(chargers[1]))
    assert created["data"][CONF_PLANT_ID] == "plant-b"
    assert "model" not in created["data"]

    import custom_components.sems_ev_connect.coordinator as coordinator_module
    real_session = coordinator_module.async_get_clientsession
    coordinator_module.async_get_clientsession = lambda hass: None
    try:
        startup_link = asyncio.run(coordinator_module.build_link(
            object(), "owner@example.com", "password", "CHARGER-B", plant_id="plant-b"
        ))
    finally:
        coordinator_module.async_get_clientsession = real_session
    assert startup_link._plant_id == "plant-b"
    ok("multi-plant setup carries the selected charger's plant id through every command")


def check_every_error_has_a_message() -> None:
    """An error key with no translation shows the customer a raw identifier."""
    p = os.path.join(ROOT, "custom_components", "sems_ev_connect", "translations", "en.json")
    strings = json.load(open(p, encoding="utf-8"))["config"]
    src = open(os.path.join(ROOT, "custom_components", "sems_ev_connect", "config_flow.py"),
               encoding="utf-8").read()
    import re
    used = set(re.findall(r'errors\["base"\]\s*=\s*"([a-z_]+)"', src))
    missing = used - set(strings["error"])
    assert not missing, f"no message for: {missing}"

    steps = set(re.findall(r'step_id="([a-z_]+)"', src))
    missing_steps = steps - set(strings["step"])
    assert not missing_steps, f"no translation for step(s): {missing_steps}"

    # The account is called SEMS Portal; there is no app called "GoodWe".
    blob = json.dumps(strings)
    assert "SEMS Portal" in blob, "the sign-in screen must name SEMS Portal"
    assert "GoodWe app" not in blob, "there is no app called GoodWe - it is SEMS Portal"
    ok(f"every error and step has a message, and they name SEMS Portal")


# ---------------------------------------------------------------- polling
def check_poll_interval_is_not_aggressive() -> None:
    """SEMS is the same API the owner's phone uses. Polling harder does not get
    fresher data and risks the account being rate-limited."""
    from custom_components.sems_ev_connect.const import DEFAULT_SCAN_INTERVAL, MIN_SCAN_INTERVAL
    assert DEFAULT_SCAN_INTERVAL >= 30, DEFAULT_SCAN_INTERVAL
    assert MIN_SCAN_INTERVAL >= 30, MIN_SCAN_INTERVAL
    ok(f"polls every {DEFAULT_SCAN_INTERVAL}s, which the cloud will tolerate")


def check_no_secrets_committed() -> None:
    import re
    bad = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for f in files:
            if not f.endswith((".py", ".json", ".md", ".yaml")):
                continue
            t = open(os.path.join(base, f), encoding="utf-8", errors="ignore").read()
            # Assembled at runtime so this file does not contain the very
            # strings it is looking for, which would make it fail on itself.
            for pat in ("sb_" + "secret_", "service" + "_role", "eyJ1IjoiaHR0" + "cHM6"):
                if pat in t:
                    bad.append((os.path.relpath(os.path.join(base, f), ROOT), pat))
    assert not bad, f"secrets in a public repo: {bad}"
    ok("no secret patterns anywhere in the repository")


def main() -> int:
    for check in (check_every_module_imports, check_manifest, check_mode_round_trip,
                  check_select_service_contract, check_sensor_values,
                  check_sensor_state_classes_are_valid,
                  check_sensors_survive_an_empty_snapshot, check_power_limit_bounds,
                  check_entities_are_uniquely_identified, check_config_flow_error_paths,
                  check_auth_failure_starts_reauthentication,
                  check_multi_plant_charger_routing,
                  check_every_error_has_a_message, check_poll_interval_is_not_aggressive,
                  check_no_secrets_committed):
        check()
    print(f"\nALL {len(PASSED)} INTEGRATION TESTS PASS "
          "(against Home Assistant and in-process fakes, not a real charger)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
