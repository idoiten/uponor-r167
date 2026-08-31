"""Climate-entiteter för Uponor R-167-rum."""

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

# Efter en ändring: hur ofta vi kollar om enheten bekräftat det nya
# värdet, och hur länge vi max håller på innan vi ger upp och låter
# den vanliga periodiska pollningen ta över istället.
_CONFIRM_INTERVAL = 5  # sekunder mellan varje försök
_CONFIRM_MAX_ATTEMPTS = 24  # ca 2 minuter totalt


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: UponorCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [
        UponorRoomClimate(coordinator, entry, room) for room in coordinator.rooms
    ]
    async_add_entities(entities)


class UponorRoomClimate(CoordinatorEntity[UponorCoordinator], ClimateEntity):
    """Ett rum/en termostatkanal på R-167."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 0.5
    _attr_has_entity_name = True
    _attr_name = None  # Huvudentiteten på enheten - använd bara enhetens (rummets) namn
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT

    def __init__(self, coordinator: UponorCoordinator, entry: ConfigEntry, room: Room) -> None:
        super().__init__(coordinator)
        self._settings_start = room.settings_start
        self._entry = entry
        self._attr_unique_id = room.unique_id
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
    def current_temperature(self) -> float | None:
        room = self._room
        return room.actual if room else None

    @property
    def target_temperature(self) -> float | None:
        room = self._room
        return room.setpoint if room else None

    @property
    def hvac_action(self):
        """Byggt på enhetens egen 'room in demand'-status, inte en gissning."""
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
        # Optimistisk uppdatering direkt, så UI:t känns responsivt.
        room.setpoint = temperature
        self.async_write_ha_state()

        # Snabb bekräftelse: läs bara det här rummets fält (inte alla
        # nio) tills "Current action" (room_in_demand) faktiskt ändras
        # från vad den var innan – det är den som normalt släpar efter
        # börvärdet. Låset i api.py gör det säkert att köra parallellt
        # med den vanliga periodiska pollningen utan att krocka.
        self.hass.async_create_task(self._confirm_after_delay(room, baseline_demand))

    async def _confirm_after_delay(self, room: Room, baseline_demand: bool | None) -> None:
        for _ in range(_CONFIRM_MAX_ATTEMPTS):
            await asyncio.sleep(_CONFIRM_INTERVAL)
            try:
                await self.coordinator.client.refresh_rooms([room])
            except UponorApiError as err:
                _LOGGER.debug(
                    "Bekräftelseförsök för %s misslyckades, försöker igen: %s",
                    room.name,
                    err,
                )
                continue
            self.async_write_ha_state()
            if room.room_in_demand != baseline_demand:
                return  # room_in_demand ändrades – sluta polla
        _LOGGER.debug(
            "room_in_demand för %s ändrades inte inom tidsgränsen, "
            "väntar på nästa ordinarie pollning istället",
            room.name,
        )
