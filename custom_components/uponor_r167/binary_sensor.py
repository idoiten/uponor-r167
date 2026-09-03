"""Problem sensor: shows whether the last call to the R-167 failed."""

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
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: UponorCoordinator = data["coordinator"]
    gateway_device_id: str = data["gateway_device_id"]
    entities: list[BinarySensorEntity] = [UponorProblemSensor(coordinator, entry)]
    for room in coordinator.rooms:
        entities += [
            UponorRoomAlarm(
                coordinator, entry, room, gateway_device_id, "rh_limit", "moisture",
                BinarySensorDeviceClass.MOISTURE,
            ),
            UponorRoomAlarm(
                coordinator, entry, room, gateway_device_id, "floor_limit", "floor",
                BinarySensorDeviceClass.PROBLEM,
            ),
            UponorRoomAlarm(
                coordinator, entry, room, gateway_device_id, "technical_alarm", "technical_alarm",
                BinarySensorDeviceClass.PROBLEM,
            ),
            UponorRoomAlarm(
                coordinator, entry, room, gateway_device_id, "tamper_alarm", "tamper_alarm",
                BinarySensorDeviceClass.TAMPER,
            ),
            UponorRoomAlarm(
                coordinator, entry, room, gateway_device_id, "rf_alarm", "rf_alarm",
                BinarySensorDeviceClass.PROBLEM,
            ),
            UponorRoomAlarm(
                coordinator, entry, room, gateway_device_id, "battery_alarm", "battery",
                BinarySensorDeviceClass.BATTERY,
            ),
        ]
    async_add_entities(entities)


class UponorProblemSensor(CoordinatorEntity[UponorCoordinator], BinarySensorEntity):
    """ON = the last call to the device failed."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "api_status"

    def __init__(self, coordinator: UponorCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "uponor_r167_problem"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["host"])},
            name="Uponor R-167",
            manufacturer="Uponor",
            model="R-167 / U@home",
            configuration_url=f"http://{entry.data['host']}",
        )

    @property
    def available(self) -> bool:
        # This entity should ALWAYS be shown, whether the device
        # responds or not - that's the whole point of it. The default
        # CoordinatorEntity would otherwise go "unavailable" as soon as
        # a poll fails.
        return True

    @property
    def is_on(self) -> bool:
        return not self.coordinator.last_update_success

    @property
    def extra_state_attributes(self):
        err = getattr(self.coordinator, "last_exception", None)
        return {"last_error": str(err)} if err else {}


class UponorRoomAlarm(CoordinatorEntity[UponorCoordinator], BinarySensorEntity):
    """An alarm/status flag per room (technical, tamper, rf, battery)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: UponorCoordinator,
        entry: ConfigEntry,
        room: Room,
        gateway_device_id: str,
        attr_name: str,
        translation_key: str,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        super().__init__(coordinator)
        self._settings_start = room.settings_start
        self._attr_name_attr = attr_name
        self._attr_device_class = device_class
        self._attr_unique_id = f"{room.unique_id}_{attr_name}"
        self._attr_translation_key = translation_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, room.unique_id)},
            name=room.name,
            manufacturer="Uponor",
            model="Thermostat (Smatrix Wave)",
            via_device_id=gateway_device_id,
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
