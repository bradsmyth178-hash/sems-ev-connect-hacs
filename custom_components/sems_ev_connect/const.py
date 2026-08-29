"""Constants for the SEMS EV CONNECT integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "sems_ev_connect"

CONF_SERIAL: Final = "serial"
CONF_MODEL: Final = "model"

# SEMS is a cloud API shared with the GoodWe app. Polling harder than this does
# not get fresher data - the bridge learned the same thing the hard way - and it
# risks the account being rate-limited, which locks the owner out of their own
# charger. Thirty seconds is the floor the SEMS client itself enforces.
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 30

# The GoodWe charge modes, in the wording the customer sees everywhere else.
# The values are the raw mode numbers the API takes.
MODE_FAST: Final = 0
MODE_SOLAR_ONLY: Final = 1
MODE_SOLAR_BATTERY: Final = 2

MODE_LABELS: Final = {
    MODE_FAST: "Fast",
    MODE_SOLAR_ONLY: "Solar only",
    MODE_SOLAR_BATTERY: "Solar + battery",
}
LABEL_TO_MODE: Final = {v: k for k, v in MODE_LABELS.items()}

# Vehicle states as the charger reports them, mapped to plain words.
CAR_LABELS: Final = {
    0: "Not plugged in",
    1: "Half connected",
    2: "Connected",
}

# 6 A on a single phase is roughly 1.4 kW, and no EV charger can go below its
# own floor - asking for less does not charge slower, it fails. The ceiling is
# whatever the unit is rated for.
MIN_CHARGE_KW: Final = 1.4
