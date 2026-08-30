# Changelog

## 1.2.0

- Adds the Home Assistant current-limit entity used by Smart Charging.
- Adds EVCC-compatible status, charging-current and charging-voltage sensors.
- Coalesces rapid current changes and verifies each applied charger limit.
- Blocks commands when the latest charger snapshot is unavailable or stale.

## 1.1.1

- Stable charging-mode values for Home Assistant automations.
- Verified control writes and improved setup diagnostics.
