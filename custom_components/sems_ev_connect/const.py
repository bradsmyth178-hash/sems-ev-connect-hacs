"""Constants for the SEMS EV CONNECT integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "sems_ev_connect"

CONF_SERIAL: Final = "serial"
CONF_PLANT_ID: Final = "plant_id"

# SEMS is a cloud API shared with the SEMS Portal app. Polling harder than this does
# not get fresher data - the bridge learned the same thing the hard way - and it
# risks the account being rate-limited, which locks the owner out of their own
# charger. Thirty seconds is the floor the SEMS client itself enforces.
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 30

# The GoodWe charge modes. The API takes the raw numbers; Home Assistant entity
# states must be stable machine keys so services and blueprints can address them.
# Friendly wording belongs in translations/en.json, not in entity state.
MODE_FAST: Final = 0
MODE_SOLAR_ONLY: Final = 1
MODE_SOLAR_BATTERY: Final = 2

MODE_KEYS: Final = {
    MODE_FAST: "fast",
    MODE_SOLAR_ONLY: "pv_priority",
    MODE_SOLAR_BATTERY: "pv_and_battery",
}
MODE_KEY_TO_VALUE: Final = {key: value for value, key in MODE_KEYS.items()}

# Stable states used by Home Assistant conditions. Their readable wording is
# translated in the frontend, while templates continue to see these keys.
CAR_KEYS: Final = {
    0: "not_plugged_in",
    1: "half_connected",
    2: "connected",
}

# 6 A on a single phase is roughly 1.4 kW, and no EV charger can go below its
# own floor - asking for less does not charge slower, it fails. The ceiling is
# whatever the unit is rated for.
MIN_CHARGE_KW: Final = 1.4
