"""Climate entities for Uponor R-167 rooms."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UponorCoordinator
from .api import Room, UponorApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# After a change: how often we check whether the device has confirmed
# the new value, and how long we keep trying before giving up and
# letting the regular periodic poll take over instead.
_CONFIRM_INTERVAL = 5  # seconds between each attempt
_CONFIRM_MAX_ATTEMPTS = 24  # roughly 2 minutes total


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: UponorCoordinator = data["coordinator"]
    gateway_device_id: str = data["gateway_device_id"]
    entities = [
        UponorRoomClimate(coordinator, entry, room, gateway_device_id)
        for room in coordinator.rooms
    ]
    async_add_entities(entities)


class UponorRoomClimate(CoordinatorEntity[UponorCoordinator], ClimateEntity):
    """A room / thermostat channel on the R-167."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 0.5
    _attr_has_entity_name = True
    _attr_name = None  # Primary entity on the device - use the device's (room's) name only
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT

    def __init__(
        self,
        coordinator: UponorCoordinator,
        entry: ConfigEntry,
        room: Room,
        gateway_device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._settings_start = room.settings_start
        self._entry = entry
        self._attr_unique_id = room.unique_id
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
    def current_temperature(self) -> float | None:
        room = self._room
        return room.actual if room else None

    @property
    def target_temperature(self) -> float | None:
        room = self._room
        return room.setpoint if room else None

    @property
    def hvac_action(self):
        """Based on the device's own 'room in demand' status, not a guess."""
        room = self._room
        if room is None or room.room_in_demand is None:
            return None
        return HVACAction.HEATING if room.room_in_demand else HVACAction.IDLE

    @property
    def min_temp(self) -> float:
        room = self._room
        return room.min_temp if room and room.min_temp is not None else 5.0

    @property
    def max_temp(self) -> float:
        room = self._room
        return room.max_temp if room and room.max_temp is not None else 35.0

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get("temperature")
        room = self._room
        if temperature is None or room is None:
            return
        baseline_demand = room.room_in_demand
        await self.coordinator.client.write_value(room.setpoint_id, temperature)
        # Optimistic update right away, so the UI feels responsive.
        room.setpoint = temperature
        self.async_write_ha_state()

        # Quick confirmation: only read this room's fields (not all
        # nine) until "Current action" (room_in_demand) actually
        # changes from what it was before - that's the one that
        # normally lags behind the setpoint. The lock in api.py makes
        # it safe to run this in parallel with the regular periodic
        # poll without colliding.
        self.hass.async_create_task(self._confirm_after_delay(room, baseline_demand))

    async def _confirm_after_delay(self, room: Room, baseline_demand: bool | None) -> None:
        for _ in range(_CONFIRM_MAX_ATTEMPTS):
            await asyncio.sleep(_CONFIRM_INTERVAL)
            try:
                await self.coordinator.client.refresh_rooms([room])
            except UponorApiError as err:
                _LOGGER.debug(
                    "Confirmation attempt for %s failed, retrying: %s",
                    room.name,
                    err,
                )
                continue
            self.async_write_ha_state()
            if room.room_in_demand != baseline_demand:
                return  # room_in_demand changed - stop polling
        _LOGGER.debug(
            "room_in_demand for %s did not change within the time limit, "
            "waiting for the next regular poll instead",
            room.name,
        )
