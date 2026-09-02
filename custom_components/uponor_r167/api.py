"""Enkel async-klient för Uponor R-167:s lokala JSON-RPC-API."""

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
    """Fel vid kommunikation med R-167."""


# Vid uppstart: hur många gånger vi försöker om vi misstänker att
# enheten svarade med skräpdata (t.ex. för att den själv fortfarande
# höll på att starta upp), och hur länge vi väntar mellan försöken.
DISCOVERY_MAX_ATTEMPTS = 5
DISCOVERY_RETRY_DELAY = 10  # sekunder


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
        property, t.ex. larm som ligger på property 662 istället för 85."""
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
        """Läs alla kanaler och returnera de som faktiskt har ett rumsnamn.

        Enheten har visat sig kunna svara med skräpdata (bl.a. rena
        siffror istället för riktiga rumsnamn) om den frågas medan den
        själv fortfarande håller på att starta upp – t.ex. om HA
        laddar om integrationen precis efter en strömavbrott/omstart
        av R-167. Om vi upptäcker sådant skräp, eller inte hittar
        några rum alls, väntar vi och försöker igen ett antal gånger
        innan vi ger upp helt (vilket gör att HA:s vanliga
        setup_retry-mekanism tar över och försöker igen senare).
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
            f"Enheten svarade med skräpdata eller inga rum hittades efter "
            f"{DISCOVERY_MAX_ATTEMPTS} försök (senast {last_room_count} rum "
            f"hittade). Enheten verkar inte vara redo."
        )

    async def _discover_once(self) -> tuple[list[Room], bool]:
        """En enskild sökning. Returnerar (rum, hittades_skräp)."""
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
                # Ett tomt/oanvänt fält är helt normalt. Men om det
                # faktiskt innehöll NÅGOT (bara inte ett giltigt namn)
                # är det ett tecken på skräpdata, inte en oanvänd kanal.
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
        chunk_size = 40
        values: dict[int, object] = {}
        for i in range(0, len(items), chunk_size):
            chunk = items[i : i + chunk_size]
            values.update(await self.read(chunk))
        for room in rooms:
            room.actual = _as_temperature(values.get(room.actual_id))
            room.setpoint = _as_temperature(values.get(room.setpoint_id))
            room.room_in_demand = _as_bool(values.get(room.room_in_demand_id))
            room.rh_limit = _as_bool(values.get(room.rh_limit_id))
            room.floor_limit = _as_bool(values.get(room.floor_limit_id))
            room.technical_alarm = _as_bool(values.get(room.technical_alarm_id))
            room.tamper_alarm = _as_bool(values.get(room.tamper_alarm_id))
            room.rf_alarm = _as_bool(values.get(room.rf_alarm_id))
            room.battery_alarm = _as_bool(values.get(room.battery_alarm_id))


_NUMERIC_ONLY = re.compile(r"^[\d.\-]+$")


def _looks_like_room_name(value: object) -> bool:
    """Ett riktigt rumsnamn är alltid människo-skrivet text.

    Enheten har visat sig kunna svara med skräpdata under instabila
    perioder – bland annat ett värde som råkar se ut som "1.1" eller
    "1.3" (troligen ett feltolkat numeriskt fält) istället för det
    riktiga rumsnamnet. Ett rent numeriskt "namn" är aldrig giltigt,
    så vi avvisar sådana istället för att skapa/döpa om ett rum till
    skräp.
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
    """Som _as_float, men avvisar orimliga värden (t.ex. skräpdata som
    visar sig som flera tusen grader, eller ett golvvärmt rum som
    visar exakt 0,0°C) istället för att visa dem rakt av."""
    f = _as_float(value)
    if f is None:
        return None
    if f < -30 or f > 60:
        return None
    if f == 0:
        return None
    return f


def _as_bool(value: object) -> bool | None:
    """Endast exakt 0 eller 1 räknas som ett giltigt booleskt värde.

    Enheten har visat sig kunna svara med skräpvärden under instabila
    perioder (t.ex. precis efter en omstart). Om vi tolkade *allt* som
    inte är exakt 0 som "på" skulle sådan skräpdata kunna se ut som ett
    gäng samtidiga larm. Ett okänt/orimligt värde ger hellre "okänt"
    (None) än ett falskt larm.
    """
    f = _as_float(value)
    if f == 0:
        return False
    if f == 1:
        return True
    return None
