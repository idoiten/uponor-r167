"""Problem-sensor: visar om senaste anropet mot R-167 misslyckades."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UponorCoordinator
from .api import Room
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: UponorCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[BinarySensorEntity] = [UponorProblemSensor(coordinator, entry)]
    for room in coordinator.rooms:
        entities += [
            UponorRoomAlarm(
                coordinator, entry, room, "rh_limit", "fukt",
                BinarySensorDeviceClass.MOISTURE,
            ),
            UponorRoomAlarm(
                coordinator, entry, room, "floor_limit", "golv",
                BinarySensorDeviceClass.PROBLEM,
            ),
            UponorRoomAlarm(
                coordinator, entry, room, "technical_alarm", "tekniskt larm",
                BinarySensorDeviceClass.PROBLEM,
            ),
            UponorRoomAlarm(
                coordinator, entry, room, "tamper_alarm", "manipulationslarm",
                BinarySensorDeviceClass.TAMPER,
            ),
            UponorRoomAlarm(
                coordinator, entry, room, "rf_alarm", "radiolarm",
                BinarySensorDeviceClass.PROBLEM,
            ),
            UponorRoomAlarm(
                coordinator, entry, room, "battery_alarm", "batteri",
                BinarySensorDeviceClass.BATTERY,
            ),
        ]
    async_add_entities(entities)


class UponorProblemSensor(CoordinatorEntity[UponorCoordinator], BinarySensorEntity):
    """PÅ = senaste anropet mot enheten misslyckades."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: UponorCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "uponor_r167_problem"
        self._attr_name = "API-status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["host"])},
            name="Uponor R-167",
            manufacturer="Uponor",
            model="R-167 / U@home",
            configuration_url=f"http://{entry.data['host']}",
        )

    @property
    def available(self) -> bool:
        # Den här entiteten ska ALLTID visas, oavsett om enheten svarar
        # eller inte – det är ju hela poängen med den. Standard-CoordinatorEntity
        # blir annars "unavailable" så fort en pollning misslyckas.
        return True

    @property
    def is_on(self) -> bool:
        return not self.coordinator.last_update_success

    @property
    def extra_state_attributes(self):
        err = getattr(self.coordinator, "last_exception", None)
        return {"senaste_fel": str(err)} if err else {}


class UponorRoomAlarm(CoordinatorEntity[UponorCoordinator], BinarySensorEntity):
    """Ett larm/statusflagga per rum (teknisk, manipulation, radio, batteri)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UponorCoordinator,
        entry: ConfigEntry,
        room: Room,
        attr_name: str,
        display_suffix: str,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        super().__init__(coordinator)
        self._settings_start = room.settings_start
        self._attr_name_attr = attr_name
        self._attr_device_class = device_class
        self._attr_unique_id = f"{room.unique_id}_{attr_name}"
        self._attr_name = display_suffix.capitalize()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, room.unique_id)},
            name=room.name,
            manufacturer="Uponor",
            model="Termostat (Smatrix Wave)",
            via_device=(DOMAIN, entry.data["host"]),
        )

    @property
    def _room(self) -> Room | None:
        for room in self.coordinator.rooms:
            if room.settings_start == self._settings_start:
                return room
        return None

    @property
    def is_on(self) -> bool | None:
        room = self._room
        if room is None:
            return None
        return getattr(room, self._attr_name_attr)
