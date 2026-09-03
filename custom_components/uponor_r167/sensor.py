"""Systemsensorer: utetemperatur (dämpad) och medelinomhustemperatur."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UponorCoordinator
from .api import Room
from .const import AVG_INDOOR_TEMP_ID, DOMAIN, OUTDOOR_TEMP_ID


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: UponorCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[SensorEntity] = [
        UponorSystemSensor(
            coordinator,
            entry,
            obj_id=OUTDOOR_TEMP_ID,
            name="Utetemperatur",
            unique_suffix="outdoor_temp",
        ),
        UponorSystemSensor(
            coordinator,
            entry,
            obj_id=AVG_INDOOR_TEMP_ID,
            name="Medelinomhustemperatur",
            unique_suffix="avg_indoor_temp",
        ),
    ]
    entities += [
        UponorRoomTemperature(coordinator, entry, room) for room in coordinator.rooms
    ]
    async_add_entities(entities)


class UponorSystemSensor(CoordinatorEntity[UponorCoordinator], SensorEntity):
    """En enskild systemövergripande temperatur (inte knuten till ett rum)."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: UponorCoordinator,
        entry: ConfigEntry,
        obj_id: int,
        name: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._obj_id = obj_id
        self._attr_name = name
        self._attr_unique_id = f"uponor_r167_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["host"])},
            name="Uponor R-167",
            manufacturer="Uponor",
            model="R-167 / U@home",
            configuration_url=f"http://{entry.data['host']}",
        )

    @property
    def native_value(self) -> float | None:
        return self.coordinator.system_values.get(self._obj_id)


class UponorRoomTemperature(CoordinatorEntity[UponorCoordinator], SensorEntity):
    """Ärvärdet (aktuell temperatur) för ett enskilt rum, som ren sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_name = "Temperatur"

    def __init__(self, coordinator: UponorCoordinator, entry: ConfigEntry, room: Room) -> None:
        super().__init__(coordinator)
        self._settings_start = room.settings_start
        self._attr_unique_id = f"{room.unique_id}_temperature"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, room.unique_id)},
            name=room.name,
            manufacturer="Uponor",
            model="Termostat (Smatrix Wave)",
            via_device=(DOMAIN, entry.data["host"]),
        )

    @property
    def native_value(self) -> float | None:
        for room in self.coordinator.rooms:
            if room.settings_start == self._settings_start:
                return room.actual
        return None
