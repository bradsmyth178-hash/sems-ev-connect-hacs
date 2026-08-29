"""Tests for the SEMS EV CONNECT Home Assistant integration.

Run: python -m tests.test_integration   (from the repository root)

These need Home Assistant installed, because half the point is proving the
integration still loads against a real one. Everything else runs offline: no
network, no GoodWe account, no charger. What cannot be proven here is behaviour
against real hardware, and nothing in this file pretends otherwise.

The charge-mode test is the one that matters most. Passing a display name where
the charger expects a number is not a loud failure - Home Assistant swallows it
and the automation reports success while the car charges in whatever mode it was
already in. That is exactly how a set of solar automations silently charged off
the grid, so the mapping is pinned in both directions.
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
        LABEL_TO_MODE, MODE_FAST, MODE_LABELS, MODE_SOLAR_BATTERY, MODE_SOLAR_ONLY)

    # Every label maps to a number, and back to the same label.
    for label, mode in LABEL_TO_MODE.items():
        assert isinstance(mode, int), f"{label} must map to a number, not {mode!r}"
        assert MODE_LABELS[mode] == label, f"{label} does not round-trip"

    assert LABEL_TO_MODE["Fast"] == MODE_FAST == 0
    assert LABEL_TO_MODE["Solar only"] == MODE_SOLAR_ONLY == 1
    assert LABEL_TO_MODE["Solar + battery"] == MODE_SOLAR_BATTERY == 2

    # The wording the customer sees, everywhere. Home Assistant's own GoodWe
    # integration says "PV priority"; ours must not, or two pages disagree.
    for stale in ("PV priority", "PV + battery", "PV & battery"):
        assert stale not in MODE_LABELS.values(), f"{stale} leaked into the customer-facing labels"

    # The select offers exactly these, in this order. Asserted on an instance,
    # because that is what Home Assistant reads - SelectEntity exposes options
    # through a property, so the class attribute is not the live value.
    from custom_components.sems_ev_connect.select import SemsModeSelect
    inst = SemsModeSelect.__new__(SemsModeSelect)
    assert inst.options == list(MODE_LABELS.values()), inst.options
    ok("charge modes round-trip: labels shown, numbers sent, no stale wording")


def check_select_rejects_unknown_option() -> None:
    """A label we do not know must raise, not quietly send nothing."""
    import asyncio

    from custom_components.sems_ev_connect.select import SemsModeSelect

    sel = SemsModeSelect.__new__(SemsModeSelect)
    try:
        asyncio.run(SemsModeSelect.async_select_option(sel, "PV priority"))
    except ValueError:
        ok("an unknown charge mode raises rather than silently doing nothing")
        return
    except Exception as err:  # noqa: BLE001
        raise AssertionError(f"expected ValueError, got {type(err).__name__}: {err}")
    raise AssertionError("an unknown charge mode was accepted")


# ---------------------------------------------------------------- entities
def check_sensor_values() -> None:
    from custom_components.sems_ev_connect.models import Snapshot
    from custom_components.sems_ev_connect.sensor import SENSORS

    live = Snapshot(ok=True, status=3, status_name="Charging", car=2, power_kw=6.8123,
                    session_kwh=12.3456, lifetime_kwh=980.5, max_power_kw=7.0,
                    mode=1, mode_name="PV priority", faults=[])
    values = {d.key: d.value(live) for d in SENSORS}

    assert values["status"] == "Charging"
    assert values["vehicle"] == "Connected"
    # The API said "PV priority"; the customer must read our wording.
    assert values["charge_mode"] == "Solar only", values["charge_mode"]
    assert values["power"] == 6.81, "power should be rounded, not raw float noise"
    assert values["session_energy"] == 12.35
    assert values["lifetime_energy"] == 980.5
    assert values["fault"] == "None"
    ok("every sensor reports the right value from a live reading")


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
        shown.update(step=step_id, errors=errors or {})
        return {"type": "form", "step_id": step_id, "errors": errors or {}}

    flow.async_show_form = fake_show
    flow.hass = object()

    class Refuses:
        async def account_probe(self):
            raise RuntimeError("SEMS sign-in was not accepted")

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

        cf.SemsLink = lambda *a, **k: NoChargers()
        asyncio.run(flow.async_step_user({"username": "a@b.com", "password": "x"}))
        assert shown["errors"].get("base") == "no_chargers", shown
    finally:
        cf.SemsLink, cf.async_get_clientsession = real_link, real_session

    # An empty form must not error before anything has been entered.
    shown.clear()
    asyncio.run(flow.async_step_user(None))
    assert shown["errors"] == {}, shown
    ok("the setup flow tells a bad password apart from an account with no charger")


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
                  check_select_rejects_unknown_option, check_sensor_values,
                  check_sensors_survive_an_empty_snapshot, check_power_limit_bounds,
                  check_entities_are_uniquely_identified, check_config_flow_error_paths,
                  check_every_error_has_a_message, check_poll_interval_is_not_aggressive,
                  check_no_secrets_committed):
        check()
    print(f"\nALL {len(PASSED)} INTEGRATION TESTS PASS "
          "(against Home Assistant and in-process fakes, not a real charger)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
