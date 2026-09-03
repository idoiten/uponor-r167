"""System sensors: outdoor temperature (damped) and average indoor temperature."""

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
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: UponorCoordinator = data["coordinator"]
    gateway_device_id: str = data["gateway_device_id"]
    entities: list[SensorEntity] = [
        UponorSystemSensor(
            coordinator,
            entry,
            obj_id=OUTDOOR_TEMP_ID,
            translation_key="outdoor_temperature",
            unique_suffix="outdoor_temp",
        ),
        UponorSystemSensor(
            coordinator,
            entry,
            obj_id=AVG_INDOOR_TEMP_ID,
            translation_key="avg_indoor_temperature",
            unique_suffix="avg_indoor_temp",
        ),
    ]
    entities += [
        UponorRoomTemperature(coordinator, entry, room, gateway_device_id)
        for room in coordinator.rooms
    ]
    async_add_entities(entities)


class UponorSystemSensor(CoordinatorEntity[UponorCoordinator], SensorEntity):
    """A single system-wide temperature (not tied to a room)."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UponorCoordinator,
        entry: ConfigEntry,
        obj_id: int,
        translation_key: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._obj_id = obj_id
        self._attr_translation_key = translation_key
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
    """The measured (actual) temperature for a single room, as a plain sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_translation_key = "temperature"

    def __init__(
        self,
        coordinator: UponorCoordinator,
        entry: ConfigEntry,
        room: Room,
        gateway_device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._settings_start = room.settings_start
        self._attr_unique_id = f"{room.unique_id}_temperature"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, room.unique_id)},
            name=room.name,
            manufacturer="Uponor",
            model="Thermostat (Smatrix Wave)",
            via_device_id=gateway_device_id,
        )

    @property
    def native_value(self) -> float | None:
        for room in self.coordinator.rooms:
            if room.settings_start == self._settings_start:
                return room.actual
        return None
