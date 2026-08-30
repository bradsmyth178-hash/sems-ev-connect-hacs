# SEMS EV CONNECT

Puts your **GoodWe EV charger** into Home Assistant.

This integration signs in with your own GoodWe SEMS Portal account and gives
you the charger as a normal Home Assistant device.

## Install

1. **HACS → three-dot menu → Custom repositories**
2. Paste `https://github.com/bradsmyth178-hash/sems-ev-connect-hacs`, choose
   **Integration**, press **Add**
3. Find **SEMS EV CONNECT** in HACS and press **Download**, then restart
   Home Assistant
4. **Settings → Devices & services → Add integration → SEMS EV CONNECT**
5. Enter the email and password you use for the GoodWe **SEMS Portal** app

You are not asked for a serial number. The account already knows which chargers
it has, so it is asked — reading a serial off a unit in a garage is the fiddliest
part of setting this up, and mistyping it fails in a way that looks like a broken
connection rather than a typo. If the account has more than one charger, you
choose from a list.

## What you get

| Entity | |
|---|---|
| **Charging** | switch — start and stop |
| **Charge mode** | select — Fast, Solar only, Solar + battery |
| **Maximum charge power** | number — bounded by what the charger can actually do |
| **Maximum charging current** | number — EVCC-compatible 6 A to the charger's rated ceiling |
| **Status**, **Vehicle state** | what the charger and the car are doing |
| **Charging power**, **Charging current**, **Charging voltage**, **Session energy** | live readings |
| **Power limit**, **Fault** | diagnostics |

## Notes worth knowing

**It polls the cloud every 30 seconds, and will not go faster.** SEMS is the same
API your phone app uses; polling harder does not get fresher data and risks the
account being rate-limited, which locks you out of your own charger.

**Charge modes use stable automation values.** Automations use `fast`,
`pv_priority` and `pv_and_battery`; Home Assistant displays those as Fast,
Solar only and Solar + battery. The stable values are validated before a
command reaches the integration, so a wording change cannot break a schedule.

**Writes are verified.** A change the charger quietly ignores is re-asserted, and
a change that will not stick raises rather than reporting success — the charger
having a different idea of its own mode than Home Assistant does is worse than an
error.

**Session energy resets each session.** It is deliberately not marked as a
total, and the integration does not invent a lifetime total that would reset
when Home Assistant restarts.

## Your solar inverter is separate

If you want charging to follow your solar, you need your inverter in Home
Assistant too. **That one is built in** — no HACS: enable Modbus TCP on the
inverter through the SolarGo app, then add **GoodWe Inverter** from
Settings → Devices & services.

## Tests

```
run-tests.cmd        (Windows)
./run-tests.sh       (macOS / Linux)
```

First run creates a `.venv` and installs Home Assistant, which takes a few
minutes; after that it is seconds. Seventeen checks cover module loading, the HACS
manifest, translated machine states, Home Assistant's select validation, sensor
metadata, power and current bounds, command coalescing, unavailable-state
blocking, authentication and reauthentication, multi-plant routing, setup error
messages, the poll floor and secret scanning.

The charge-mode check exercises Home Assistant's validation before the handler,
then proves the accepted machine key becomes the correct numeric SEMS command.

**Read the Home Assistant version the suite prints.** pip installs the newest
Home Assistant your Python supports, so Python 3.11 gets 2024.3.3 while 3.13
gets a current one. On an old interpreter the import check proves the
integration loads against a two-year-old Home Assistant, not against the one
you are running. Install a newer Python if you want that gap closed.

Nothing here talks to a real charger, and nothing here can.

MIT licensed.
