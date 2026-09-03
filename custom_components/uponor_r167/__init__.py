"""Uponor R-167 (U@home) integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import UponorApiClient, UponorApiError, _as_outdoor_temperature, _as_temperature
from .const import (
    AVG_INDOOR_TEMP_ID,
    CONF_MAX_CHANNELS,
    CONF_SCAN_INTERVAL,
    DEFAULT_MAX_CHANNELS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OUTDOOR_TEMP_ID,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["climate", "sensor", "binary_sensor"]

# Systemövergripande värden (inte knutna till ett specifikt rum).
SYSTEM_VALUE_IDS = [AVG_INDOOR_TEMP_ID, OUTDOOR_TEMP_ID]


class UponorCoordinator(DataUpdateCoordinator):
    """Håller koll på alla rum och uppdaterar dem periodiskt."""

    def __init__(self, hass: HomeAssistant, client: UponorApiClient, interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.rooms: list = []
        self.system_values: dict[int, float] = {}
        self._discovered = False

    async def _async_update_data(self):
        try:
            if not self._discovered:
                self.rooms = await self.client.discover_and_read()
                self._discovered = True
                _LOGGER.info(
                    "Uponor R-167: hittade %d rum: %s",
                    len(self.rooms),
                    ", ".join(r.name for r in self.rooms),
                )
            else:
                await self.client.refresh_rooms(self.rooms)
            raw_system_values = await self.client.read(SYSTEM_VALUE_IDS)
            self.system_values = {
                OUTDOOR_TEMP_ID: _as_outdoor_temperature(
                    raw_system_values.get(OUTDOOR_TEMP_ID)
                ),
                AVG_INDOOR_TEMP_ID: _as_temperature(
                    raw_system_values.get(AVG_INDOOR_TEMP_ID)
                ),
            }
        except UponorApiError as err:
            raise UpdateFailed(str(err)) from err
        return self.rooms


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # R-167 har en väldigt enkel inbyggd webbserver som ofta tappar
    # anslutningen om vi återanvänder en keep-alive-koppling (t.ex. HA:s
    # delade session). Skapa därför en egen session som alltid stänger
    # anslutningen efter varje anrop.
    connector = aiohttp.TCPConnector(force_close=True, limit_per_host=1)
    session = aiohttp.ClientSession(connector=connector)

    client = UponorApiClient(
        host=entry.data["host"],
        session=session,
        max_channels=entry.options.get(
            CONF_MAX_CHANNELS,
            entry.data.get(CONF_MAX_CHANNELS, DEFAULT_MAX_CHANNELS),
        ),
    )
    interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    coordinator = UponorCoordinator(hass, client, interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "session": session,
    }

    # Skapa gateway-enheten explicit innan plattformarna sätts upp, så att
    # rummens via_device-referens alltid pekar på en enhet som redan finns
    # (annars varnar/kraschar HA beroende på i vilken ordning entiteter
    # råkar läggas till).
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data["host"])},
        name="Uponor R-167",
        manufacturer="Uponor",
        model="R-167 / U@home",
        configuration_url=f"http://{entry.data['host']}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ladda om integrationen när användaren ändrar inställningar (t.ex. scan_interval)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        stored = hass.data[DOMAIN].pop(entry.entry_id)
        await stored["session"].close()
    return unloaded
