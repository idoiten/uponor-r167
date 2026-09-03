# Uponor R-167 (U@home) for Home Assistant

Custom Home Assistant integration for Uponor Smatrix Wave PLUS via the
**R-167 (U@home)** communication module. Built directly on the module's
local JSON-RPC API (`http://<IP>/api`), reverse-engineered from scratch.

## Features

- One `climate` entity per room (thermostat channel), with `Current action`
  (Heating/Idle) based on the device's own "room in demand" status.
- One temperature sensor per room.
- Outdoor temperature and average indoor temperature (system values).
- Per-room alarms/diagnostics: technical alarm, tamper alarm, rf alarm,
  low battery, moisture limit, floor limit.
- An "API Status" sensor showing whether the last call to the device
  failed.
- Fast confirmation after a temperature change: polls the changed room
  every 5 seconds (up to 2 minutes) until the device's "room in demand"
  actually changes, instead of waiting for the next regular poll.
- All entities are neatly grouped: a gateway device ("Uponor R-167") with
  each room as its own sub-device.

## Installation

### Via HACS (recommended)

1. HACS → Integrations → menu (⋮) → **Custom repositories**.
2. Add the repo URL, category **Integration**.
3. Search for "Uponor R-167" in HACS and install.
4. Restart Home Assistant.
5. Settings → Devices & services → Add integration → search "Uponor",
   enter the IP address of your R-167.

### Manual

Copy `custom_components/uponor_r167` to your
`<config>/custom_components/` folder, restart HA, and add the
integration as above.

## Configuration

Under the integration's **Configure** button you can adjust afterwards:
- **Max channels** - how many internal channel slots are scanned on
  startup (default 30, plenty for most installations).
- **Scan interval** - how often the whole system is polled, in seconds
  (default 60).

## Background

The R-167's API is not officially documented by Uponor. The object ids
and properties in this integration were derived through manual
reverse-engineering (comparing known values against API responses,
broadly searching for BACnet object names via property 77, etc.). Works
with a Smatrix Wave PLUS installation (X-165 + R-167); not tested
against X-265/R-208.

## Disclaimer

Unofficial integration, not developed or supported by Uponor. Use at
your own risk.
