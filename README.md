# SEMS EV CONNECT

Puts a **GoodWe HCA EV charger** into Home Assistant.

The first-generation HCA charger has no local control protocol — no Modbus, no
LAN API, no OCPP of its own — so nothing on your home network can reach it. It
is reachable only through GoodWe's SEMS cloud. This integration signs in with
your own GoodWe SEMS Portal account and gives you the charger as a normal Home Assistant
device.

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
| **Status**, **Vehicle** | what the charger and the car are doing |
| **Charging power**, **Session energy**, **Total energy** | live readings |
| **Power limit**, **Fault** | diagnostics |

## Notes worth knowing

**It polls the cloud every 30 seconds, and will not go faster.** SEMS is the same
API your phone app uses; polling harder does not get fresher data and risks the
account being rate-limited, which locks you out of your own charger.

**Charge modes are sent as machine values, not labels.** Home Assistant's own
GoodWe wording differs from ours ("PV priority" versus "Solar only"). This
integration shows the friendlier words and sends the value the charger expects,
so automations cannot fail silently by passing a display name.

**Writes are verified.** A change the charger quietly ignores is re-asserted, and
a change that will not stick raises rather than reporting success — the charger
having a different idea of its own mode than Home Assistant does is worse than an
error.

**Session energy resets each session.** It is deliberately not marked as a total,
so it will not corrupt the Energy dashboard. Use **Total energy** for that.

## Your solar inverter is separate

If you want charging to follow your solar, you need your inverter in Home
Assistant too. **That one is built in** — no HACS: enable Modbus TCP on the
inverter through the SolarGo app, then add **GoodWe Inverter** from
Settings → Devices & services.

## Credits

The SEMS client here is the one from the Sunlands bridge, written against a
documented API reference and exercised against a hardware simulator. The choice
of which entities to expose follows the ground already covered by
[prezervos/goodwe-wallbox-sems-home-assistant](https://github.com/prezervos/goodwe-wallbox-sems-home-assistant)
(MIT), which is worth a look if you want the local-Modbus path for a G2 charger.

MIT licensed.
