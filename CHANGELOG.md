# Changelog

All notable changes to this project are documented here.
The format loosely follows [Keep a Changelog](https://keepachangelog.com/),
and the project aims for [Semantic Versioning](https://semver.org/).

## [1.5.0] - 2026-09-03

### Added
- **Swedish translation.** The integration's UI text (config flow /
  options flow) is now written in English by default
  (`strings.json` / `translations/en.json`), with a separate Swedish
  translation available at `translations/sv.json`.

### Changed
- **All source code (comments, docstrings, log messages) translated
  to English.** README and this changelog are now written in
  English too.
- `manifest.json`'s `documentation` and `issue_tracker` links now
  point to the real repository
  (https://github.com/idoiten/uponor-r167) instead of a placeholder.

### Fixed
- **Deprecation warning on Home Assistant 2026.9+:** replaced the
  deprecated `via_device` parameter (in `climate.py`, `sensor.py`,
  and `binary_sensor.py`) with `via_device_id`, which will otherwise
  stop working in Home Assistant 2027.8.0. The gateway device's id is
  now captured once in `__init__.py` and passed down to each
  platform's entities.

## [1.4.0] - 2026-09-02

### Added
- **Protection against garbage data during normal operation, not just
  at startup.** 1.3.0 only protected the one-time run that discovers
  the rooms. After a stress test (the module was restarted while the
  integration was already running), it turned out that the regular,
  ongoing poll (every 60 seconds) lacked the same protection - which
  could produce false alarms and a setpoint of −17.8°C. Three new
  protections in the ongoing poll:
  - **Alarms now require confirmation from two consecutive polls**
    before they're shown or trigger automations. A single odd
    reading (e.g. an alarm that flickers on once and then goes back)
    is silently ignored instead of showing up in HA.
  - **The actual (measured) temperature rejects a new reading that
    deviates more than 1°C** from the last confirmed value - a
    floor-heated room never changes that fast in reality.
  - **The setpoint is validated against the room's own min/max
    limits** (fetched once at startup) instead of just the general
    range. That would have caught −17.8°C immediately, since it's
    far outside a reasonable 15-25°C span.

### Changed
- **Tighter temperature bounds.** Room temperatures (actual, setpoint,
  min/max) now accept **5-40°C** instead of −30-60°C. The outdoor
  temperature has its own, wider bound of **−30-40°C**, since it can
  reasonably get much colder than a room. The average indoor
  temperature and outdoor temperature (system sensors) previously had
  **no** sanity check at all - they have one now too.

## [1.3.0] - 2026-09-02

### Added
- **Protection against garbage data at startup: wait and retry.**
  Room discovery (`discover_and_read`) now runs up to **5 attempts**
  with a **10-second pause** between each, if it suspects garbage
  data (e.g. a room whose name field contained something other than
  a valid text name, like "1.1") or found no rooms at all. An empty
  field (unused channel) doesn't count as garbage - only a field that
  actually contained something invalid.
- If all 5 attempts fail, the integration gives up entirely instead
  of starting with an incomplete/incorrect picture of the rooms -
  this triggers Home Assistant's built-in `setup_retry` mechanism,
  which keeps trying automatically with increasing intervals.

## [1.2.1] - 2026-09-02

### Fixed
- **Room names could become garbage if the integration was reloaded
  while the R-167 itself was still starting up** (confirmed via a
  deliberate stress test: the network cable was pulled and
  reconnected, and the integration was reloaded before the device had
  finished starting). During that window the device's web server
  responds, but with uninitialized default values instead of real
  data - which could, among other things, rename a real room (e.g.
  Klädvård) to "1.1" in HA's device registry, since the code blindly
  accepted any non-empty string. Purely numeric values (like "1.1",
  "1.3") are now explicitly rejected; a room with such a "name" is
  skipped in that scan instead of being created/renamed to garbage.
- The same stress test also produced an implausible temperature
  reading (0.0°C for a room with no active rf or battery alarm).
  Temperature values of exactly **0.0°C are now also rejected**, in
  addition to the previous range filter (−30°C to 60°C) - a
  floor-heated room should never show exactly 0°C in practice; such a
  value is always garbage data, not a real reading.

## [1.2.0] - 2026-09-02

### Fixed
- **Protection against garbage data from the device during unstable
  periods** (e.g. right after a physical restart of the R-167).
  Previously, a single odd reading could be interpreted as "several
  thousand degrees" or trigger false alarms simultaneously throughout
  the house. Now:
  - Alarms only accept exactly `0` or `1` - anything else becomes
    "unknown" instead of a false "on".
  - Temperature values outside a reasonable range (−30°C to 60°C) are
    rejected and shown as "unknown" instead of the obviously
    incorrect number.
  - The startup discovery (which queries ~300 objects) is now split
    into smaller batches of 40 objects at a time, instead of one big
    call. This is gentler on the device's weak built-in web server
    and reduces the risk of the whole integration getting stuck at
    startup, even when the web UI (which makes smaller calls)
    continues to work fine.

## [1.1.0] - 2026-08-31

### Fixed (important!)
- **The alarms (technical alarm, tamper alarm, rf alarm, battery)
  read the wrong property and therefore never showed a real alarm.**
  They used property `538` with inverted logic (`1=OK`, `0=alarm`) -
  but that was simply the wrong property. Confirmed via Chrome
  DevTools against the device's own web UI: the correct one is
  property **`662`**, with **straight** logic (`1=alarm`, `0=OK`).
  Verified by physically pulling the battery out of a thermostat and
  comparing against a known-OK room.
- Earlier tests of `538` happened to always show `1` (false "OK")
  because many fields in the API default to `1`, which gave a
  misleading confirmation of the wrong property.

## [1.0.3] - 2026-08-31

### Fixed
- Removed an incorrect duplicate of `hacs.json` that lived inside
  `custom_components/uponor_r167/` (it should only be in the repo
  root) - that was the real reason HACS never showed the updated
  name.

## [1.0.2] - 2026-08-31

### Changed
- Fixed `hacs.json`'s name from the old "Uponor R-167 (U@home)" to
  "Uponor", so the HACS dashboard shows the correct title.

### Known issue
- The HACS dashboard shows "icon not available" even though the
  integration has its own `brand/icon.png`. This is an open bug in
  HACS itself
  ([hacs/integration#5171](https://github.com/hacs/integration/issues/5171)) -
  the icon already works correctly on the Integrations page and the
  device pages in HA.

## [1.0.1] - 2026-08-31

### Added
- Custom icon (`brand/icon.png`, `brand/icon@2x.png`) shown in HA's
  integration list and on the device pages, without needing a PR
  against home-assistant/brands (supported as of HA 2026.3).

## [1.0.0] - 2026-08-31

First working version.

### Added
- One `climate` entity per room, with `Current action` (Heating/Idle)
  based on the device's own "room in demand" status.
- Temperature sensor per room.
- System sensors: outdoor temperature and average indoor temperature.
- Alarm/diagnostic sensors per room: technical alarm, tamper alarm,
  rf alarm, low battery, moisture limit, floor limit.
- API status sensor (shows whether the last call to the device
  failed).
- Fast confirmation after a temperature change: polls the changed
  room every 5 seconds (up to 2 minutes) until `Current action`
  actually changes, instead of waiting for the next regular poll.
- Separate device per room, grouped under a shared gateway device.
- Configurable `max_channels` and `scan_interval` via the
  integration's Options Flow (Configure button), no reinstall
  required.
- HACS support.
