"""Simple async client for the Uponor R-167's local JSON-RPC API."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

import aiohttp

from .const import (
    CHANNEL_STRIDE,
    DATA_OFFSET,
    OFFSET_ACTUAL,
    OFFSET_BATTERY_ALARM,
    OFFSET_FLOOR_LIMIT,
    OFFSET_MAX,
    OFFSET_MIN,
    OFFSET_NAME,
    OFFSET_RF_ALARM,
    OFFSET_RH_LIMIT,
    OFFSET_ROOM_IN_DEMAND,
    OFFSET_SETPOINT,
    OFFSET_TAMPER,
    OFFSET_TECHNICAL_ALARM,
)


class UponorApiError(Exception):
    """Error communicating with the R-167."""


# At startup: how many times we retry if we suspect the device
# responded with garbage data (e.g. because it was still starting up
# itself), and how long we wait between attempts.
DISCOVERY_MAX_ATTEMPTS = 5
DISCOVERY_RETRY_DELAY = 10  # seconds


@dataclass
class Room:
    """A thermostat channel (room)."""

    settings_start: int
    name: str
    actual: float | None = None
    setpoint: float | None = None
    min_temp: float | None = None
    max_temp: float | None = None
    room_in_demand: bool | None = None
    rh_limit: bool | None = None
    floor_limit: bool | None = None
    technical_alarm: bool | None = None
    tamper_alarm: bool | None = None
    rf_alarm: bool | None = None
    battery_alarm: bool | None = None

    # Unconfirmed "candidate values" for alarm debouncing (see
    # _debounce_bool). Not meant to be read directly by entities -
    # internal bookkeeping only.
    _pending_technical_alarm: bool | None = None
    _pending_tamper_alarm: bool | None = None
    _pending_rf_alarm: bool | None = None
    _pending_battery_alarm: bool | None = None

    @property
    def unique_id(self) -> str:
        return f"uponor_r167_{self.settings_start}"

    @property
    def setpoint_id(self) -> int:
        return self.settings_start + OFFSET_SETPOINT

    @property
    def room_in_demand_id(self) -> int:
        return self.settings_start + OFFSET_ROOM_IN_DEMAND

    @property
    def rh_limit_id(self) -> int:
        return self.settings_start + OFFSET_RH_LIMIT

    @property
    def floor_limit_id(self) -> int:
        return self.settings_start + OFFSET_FLOOR_LIMIT

    @property
    def technical_alarm_id(self) -> int:
        return self.settings_start + OFFSET_TECHNICAL_ALARM

    @property
    def tamper_alarm_id(self) -> int:
        return self.settings_start + OFFSET_TAMPER

    @property
    def rf_alarm_id(self) -> int:
        return self.settings_start + OFFSET_RF_ALARM

    @property
    def battery_alarm_id(self) -> int:
        return self.settings_start + OFFSET_BATTERY_ALARM

    @property
    def min_id(self) -> int:
        return self.settings_start + OFFSET_MIN

    @property
    def max_id(self) -> int:
        return self.settings_start + OFFSET_MAX

    @property
    def actual_id(self) -> int:
        return self.settings_start + DATA_OFFSET + OFFSET_ACTUAL

    @property
    def name_id(self) -> int:
        return self.settings_start + DATA_OFFSET + OFFSET_NAME


@dataclass
class UponorApiClient:
    """Talks to http://<host>/api (JSON-RPC 2.0, method read/write)."""

    host: str
    session: aiohttp.ClientSession
    max_channels: int = 30
    timeout: float = 10.0

    _next_id: int = field(default=1, init=False, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    @property
    def url(self) -> str:
        return f"http://{self.host}/api"

    def _rpc_id(self) -> int:
        self._next_id += 1
        return self._next_id

    async def _call(self, method: str, objects: list[dict]) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": self._rpc_id(),
            "method": method,
            "params": {"objects": objects},
        }
        # The R-167 has a very simple/weak built-in web server that
        # can't handle overlapping calls - make sure only ONE call at
        # a time is ever sent to the device, whether it comes from a
        # periodic poll or a user-initiated write.
        async with self._lock:
            last_err: Exception | None = None
            for attempt in range(5):
                try:
                    async with self.session.post(
                        self.url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        headers={"Connection": "close"},
                    ) as resp:
                        resp.raise_for_status()
                        return await resp.json()
                except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                    last_err = err
                    # Give the device plenty of time to catch its
                    # breath, especially after a write (which may
                    # involve a flash write).
                    await asyncio.sleep(1.0 * (attempt + 1))
            raise UponorApiError(f"Could not reach {self.url}: {last_err}") from last_err

    async def read(self, items: list[int] | list[tuple[int, str]]) -> dict[int, object]:
        """Read objects. Each item is either an id (property 85 is
        assumed) or an (id, property) pair for objects that use a
        different property, e.g. alarms which live on property 662
        instead of 85."""
        normalized = [
            (i, "85") if isinstance(i, int) else (i[0], i[1]) for i in items
        ]
        objects = [
            {"id": str(i), "properties": {prop: {}}} for i, prop in normalized
        ]
        body = await self._call("read", objects)
        result = body.get("result")
        if not isinstance(result, dict):
            raise UponorApiError(f"Unexpected response: {body}")
        values: dict[int, object] = {}
        for obj in result.get("objects", []):
            props = obj.get("properties", {})
            for prop_value in props.values():
                if isinstance(prop_value, dict) and "value" in prop_value:
                    values[int(obj["id"])] = prop_value["value"]
                    break
        return values

    async def write_value(self, obj_id: int, value: float) -> None:
        body = await self._call(
            "write",
            [{"id": str(obj_id), "properties": {"85": {"value": str(value)}}}],
        )
        if body.get("result") != "ok":
            raise UponorApiError(f"Write failed: {body}")

    ALARM_PROPERTY = "662"

    def _all_ids(self) -> list[tuple[int, str]]:
        items: list[tuple[int, str]] = []
        for n in range(self.max_channels):
            settings_start = CHANNEL_STRIDE * n
            data_start = settings_start + DATA_OFFSET
            items += [
                (settings_start + OFFSET_MIN, "85"),
                (settings_start + OFFSET_MAX, "85"),
                (settings_start + OFFSET_SETPOINT, "85"),
                (settings_start + OFFSET_ROOM_IN_DEMAND, "85"),
                (settings_start + OFFSET_RH_LIMIT, "85"),
                (settings_start + OFFSET_FLOOR_LIMIT, "85"),
                (settings_start + OFFSET_TECHNICAL_ALARM, self.ALARM_PROPERTY),
                (settings_start + OFFSET_TAMPER, self.ALARM_PROPERTY),
                (settings_start + OFFSET_RF_ALARM, self.ALARM_PROPERTY),
                (settings_start + OFFSET_BATTERY_ALARM, self.ALARM_PROPERTY),
                (data_start + OFFSET_ACTUAL, "85"),
                (data_start + OFFSET_NAME, "85"),
            ]
        return items

    async def discover_and_read(self) -> list[Room]:
        """Read all channels and return the ones that actually have a
        room name.

        The device has been observed to respond with garbage data
        (e.g. plain numbers instead of real room names) if queried
        while it's still starting up itself - e.g. if HA reloads the
        integration right after a power outage/restart of the R-167.
        If we detect such garbage, or find no rooms at all, we wait
        and retry a number of times before giving up entirely (which
        lets HA's regular setup_retry mechanism take over and try
        again later).
        """
        last_room_count = 0
        for attempt in range(DISCOVERY_MAX_ATTEMPTS):
            rooms, garbage_detected = await self._discover_once()
            last_room_count = len(rooms)
            if rooms and not garbage_detected:
                return rooms
            if attempt < DISCOVERY_MAX_ATTEMPTS - 1:
                await asyncio.sleep(DISCOVERY_RETRY_DELAY)
        raise UponorApiError(
            f"The device responded with garbage data or no rooms were "
            f"found after {DISCOVERY_MAX_ATTEMPTS} attempts (last saw "
            f"{last_room_count} rooms). The device doesn't seem ready."
        )

    async def _discover_once(self) -> tuple[list[Room], bool]:
        """A single search. Returns (rooms, garbage_found)."""
        all_items = self._all_ids()
        chunk_size = 40
        values: dict[int, object] = {}
        for i in range(0, len(all_items), chunk_size):
            chunk = all_items[i : i + chunk_size]
            values.update(await self.read(chunk))

        rooms: list[Room] = []
        garbage_detected = False
        for n in range(self.max_channels):
            settings_start = CHANNEL_STRIDE * n
            data_start = settings_start + DATA_OFFSET
            name = values.get(data_start + OFFSET_NAME)
            if not _looks_like_room_name(name):
                # An empty/unused field is completely normal. But if
                # it actually contained SOMETHING (just not a valid
                # name), that's a sign of garbage data, not an unused
                # channel.
                if isinstance(name, str) and name.strip():
                    garbage_detected = True
                continue
            rooms.append(
                Room(
                    settings_start=settings_start,
                    name=name.strip(),
                    actual=_as_temperature(values.get(data_start + OFFSET_ACTUAL)),
                    setpoint=_as_temperature(values.get(settings_start + OFFSET_SETPOINT)),
                    min_temp=_as_temperature(values.get(settings_start + OFFSET_MIN)),
                    max_temp=_as_temperature(values.get(settings_start + OFFSET_MAX)),
                    room_in_demand=_as_bool(
                        values.get(settings_start + OFFSET_ROOM_IN_DEMAND)
                    ),
                    rh_limit=_as_bool(values.get(settings_start + OFFSET_RH_LIMIT)),
                    floor_limit=_as_bool(values.get(settings_start + OFFSET_FLOOR_LIMIT)),
                    technical_alarm=_as_bool(
                        values.get(settings_start + OFFSET_TECHNICAL_ALARM)
                    ),
                    tamper_alarm=_as_bool(values.get(settings_start + OFFSET_TAMPER)),
                    rf_alarm=_as_bool(values.get(settings_start + OFFSET_RF_ALARM)),
                    battery_alarm=_as_bool(
                        values.get(settings_start + OFFSET_BATTERY_ALARM)
                    ),
                )
            )
        return rooms, garbage_detected

    async def refresh_rooms(self, rooms: list[Room]) -> None:
        """Update actual/setpoint/status/alarms (not min/max/name) for already known rooms."""
        items: list[tuple[int, str]] = []
        for room in rooms:
            items += [
                (room.actual_id, "85"),
                (room.setpoint_id, "85"),
                (room.room_in_demand_id, "85"),
                (room.rh_limit_id, "85"),
                (room.floor_limit_id, "85"),
                (room.technical_alarm_id, self.ALARM_PROPERTY),
                (room.tamper_alarm_id, self.ALARM_PROPERTY),
                (room.rf_alarm_id, self.ALARM_PROPERTY),
                (room.battery_alarm_id, self.ALARM_PROPERTY),
            ]
        chunk_size = 40
        values: dict[int, object] = {}
        for i in range(0, len(items), chunk_size):
            chunk = items[i : i + chunk_size]
            values.update(await self.read(chunk))
        for room in rooms:
            # Actual temperature: reject a new reading that deviates
            # more than 1°C from the last confirmed value - a
            # floor-heated room never changes that fast in practice,
            # so a bigger jump is garbage data.
            new_actual = _as_temperature(values.get(room.actual_id))
            if new_actual is not None:
                if room.actual is None or abs(new_actual - room.actual) <= 1.0:
                    room.actual = new_actual
                # otherwise: keep the old, confirmed value

            # Setpoint: reject values outside the room's own min/max
            # limits (fetched once at startup) - e.g. -17.8°C would be
            # caught here even though it passes the general 5-40°C
            # filter meant for a different room with wider limits.
            new_setpoint = _as_temperature(values.get(room.setpoint_id))
            if new_setpoint is not None:
                within_limits = True
                if room.min_temp is not None and new_setpoint < room.min_temp:
                    within_limits = False
                if room.max_temp is not None and new_setpoint > room.max_temp:
                    within_limits = False
                if within_limits:
                    room.setpoint = new_setpoint
                # otherwise: keep the old, confirmed value

            room.room_in_demand = _as_bool(values.get(room.room_in_demand_id))
            room.rh_limit = _as_bool(values.get(room.rh_limit_id))
            room.floor_limit = _as_bool(values.get(room.floor_limit_id))

            # Alarms: require the same value to be seen on two
            # consecutive polls before it's shown/triggers automations
            # (see _debounce_bool).
            room.technical_alarm, room._pending_technical_alarm = _debounce_bool(
                room.technical_alarm,
                room._pending_technical_alarm,
                _as_bool(values.get(room.technical_alarm_id)),
            )
            room.tamper_alarm, room._pending_tamper_alarm = _debounce_bool(
                room.tamper_alarm,
                room._pending_tamper_alarm,
                _as_bool(values.get(room.tamper_alarm_id)),
            )
            room.rf_alarm, room._pending_rf_alarm = _debounce_bool(
                room.rf_alarm,
                room._pending_rf_alarm,
                _as_bool(values.get(room.rf_alarm_id)),
            )
            room.battery_alarm, room._pending_battery_alarm = _debounce_bool(
                room.battery_alarm,
                room._pending_battery_alarm,
                _as_bool(values.get(room.battery_alarm_id)),
            )


_NUMERIC_ONLY = re.compile(r"^[\d.\-]+$")


def _looks_like_room_name(value: object) -> bool:
    """A real room name is always human-typed text.

    The device has been observed to respond with garbage data during
    unstable periods - including a value that happens to look like
    "1.1" or "1.3" (likely a misread numeric field) instead of the
    real room name. A purely numeric "name" is never valid, so we
    reject those instead of creating/renaming a room to garbage.
    """
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return False
    if _NUMERIC_ONLY.match(stripped):
        return False
    return True


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _as_temperature(value: object) -> float | None:
    """Like _as_float, but rejects implausible values for a room
    temperature (actual, setpoint, min/max) - applies to everything
    except the outdoor temperature, which has its own, wider bound
    (see _as_outdoor_temperature)."""
    f = _as_float(value)
    if f is None:
        return None
    if f < 5 or f > 40:
        return None
    return f


def _as_outdoor_temperature(value: object) -> float | None:
    """Like _as_temperature, but with a wider bound since the outdoor
    temperature can reasonably get a lot colder than a room."""
    f = _as_float(value)
    if f is None:
        return None
    if f < -30 or f > 40:
        return None
    return f


def _debounce_bool(
    current: bool | None, pending: bool | None, new: bool | None
) -> tuple[bool | None, bool | None]:
    """Requires a new alarm value to be confirmed by two consecutive
    polls before it's shown/triggers automations, to protect against
    isolated garbage readings (e.g. right after the device recovers).

    Returns (new_confirmed_value, new_candidate).
    """
    if new is None:
        return current, pending  # unknown/unparseable response - no change
    if new == current:
        return current, None  # matches the already-confirmed value
    if new == pending:
        return new, None  # confirmed by two consecutive polls
    return current, new  # new, unconfirmed candidate


def _as_bool(value: object) -> bool | None:
    """Only exactly 0 or 1 counts as a valid boolean value.

    The device has been observed to respond with garbage values during
    unstable periods (e.g. right after a restart). If we treated
    *anything* not exactly 0 as "on", such garbage data could look
    like a bunch of simultaneous alarms. An unknown/implausible value
    yields "unknown" (None) rather than a false alarm.
    """
    f = _as_float(value)
    if f == 0:
        return False
    if f == 1:
        return True
    return None
