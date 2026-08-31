"""Enkel async-klient för Uponor R-167:s lokala JSON-RPC-API."""

from __future__ import annotations

import asyncio
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
    """Fel vid kommunikation med R-167."""


@dataclass
class Room:
    """En termostat-kanal (rum)."""

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
    """Pratar med http://<host>/api (JSON-RPC 2.0, method read/write)."""

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
        # R-167 har en väldigt enkel/svag inbyggd webbserver som inte klarar
        # av överlappande anrop – se till att bara ETT anrop i taget någonsin
        # skickas till enheten, oavsett om det kommer från en periodisk
        # pollning eller en användarinitierad skrivning.
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
                    # Ge enheten gott om tid att hämta andan, särskilt efter
                    # en skrivning (som kan innebära en flash-skrivning).
                    await asyncio.sleep(1.0 * (attempt + 1))
            raise UponorApiError(f"Kunde inte nå {self.url}: {last_err}") from last_err

    async def read(self, items: list[int] | list[tuple[int, str]]) -> dict[int, object]:
        """Läs objekt. Varje item är antingen ett id (property 85 antas)
        eller ett (id, property)-par för objekt som använder en annan
        property, t.ex. larm som ligger på property 538 istället för 85."""
        normalized = [
            (i, "85") if isinstance(i, int) else (i[0], i[1]) for i in items
        ]
        objects = [
            {"id": str(i), "properties": {prop: {}}} for i, prop in normalized
        ]
        body = await self._call("read", objects)
        result = body.get("result")
        if not isinstance(result, dict):
            raise UponorApiError(f"Oväntat svar: {body}")
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
            raise UponorApiError(f"Skrivning misslyckades: {body}")

    ALARM_PROPERTY = "538"

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
        """Läs alla kanaler och returnera de som faktiskt har ett rumsnamn."""
        values = await self.read(self._all_ids())
        rooms: list[Room] = []
        for n in range(self.max_channels):
            settings_start = CHANNEL_STRIDE * n
            data_start = settings_start + DATA_OFFSET
            name = values.get(data_start + OFFSET_NAME)
            if not isinstance(name, str) or not name.strip():
                continue
            rooms.append(
                Room(
                    settings_start=settings_start,
                    name=name.strip(),
                    actual=_as_float(values.get(data_start + OFFSET_ACTUAL)),
                    setpoint=_as_float(values.get(settings_start + OFFSET_SETPOINT)),
                    min_temp=_as_float(values.get(settings_start + OFFSET_MIN)),
                    max_temp=_as_float(values.get(settings_start + OFFSET_MAX)),
                    room_in_demand=_as_bool(
                        values.get(settings_start + OFFSET_ROOM_IN_DEMAND)
                    ),
                    rh_limit=_as_bool(values.get(settings_start + OFFSET_RH_LIMIT)),
                    floor_limit=_as_bool(values.get(settings_start + OFFSET_FLOOR_LIMIT)),
                    technical_alarm=_as_alarm_bool(
                        values.get(settings_start + OFFSET_TECHNICAL_ALARM)
                    ),
                    tamper_alarm=_as_alarm_bool(values.get(settings_start + OFFSET_TAMPER)),
                    rf_alarm=_as_alarm_bool(values.get(settings_start + OFFSET_RF_ALARM)),
                    battery_alarm=_as_alarm_bool(
                        values.get(settings_start + OFFSET_BATTERY_ALARM)
                    ),
                )
            )
        return rooms

    async def refresh_rooms(self, rooms: list[Room]) -> None:
        """Uppdatera actual/setpoint/status/larm (inte min/max/namn) för redan kända rum."""
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
        values = await self.read(items)
        for room in rooms:
            room.actual = _as_float(values.get(room.actual_id))
            room.setpoint = _as_float(values.get(room.setpoint_id))
            room.room_in_demand = _as_bool(values.get(room.room_in_demand_id))
            room.rh_limit = _as_bool(values.get(room.rh_limit_id))
            room.floor_limit = _as_bool(values.get(room.floor_limit_id))
            room.technical_alarm = _as_alarm_bool(values.get(room.technical_alarm_id))
            room.tamper_alarm = _as_alarm_bool(values.get(room.tamper_alarm_id))
            room.rf_alarm = _as_alarm_bool(values.get(room.rf_alarm_id))
            room.battery_alarm = _as_alarm_bool(values.get(room.battery_alarm_id))


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _as_bool(value: object) -> bool | None:
    f = _as_float(value)
    if f is None:
        return None
    return f != 0


def _as_alarm_bool(value: object) -> bool | None:
    """Larmfälten är omvända: 1 = OK/inget larm, 0 = larm aktivt."""
    f = _as_float(value)
    if f is None:
        return None
    return f == 0
