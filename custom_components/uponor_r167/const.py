"""Constants for the Uponor R-167 integration."""

DOMAIN = "uponor_r167"

CONF_MAX_CHANNELS = "max_channels"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_MAX_CHANNELS = 30
DEFAULT_SCAN_INTERVAL = 60  # sekunder

# Fast layout: varje kanal upptar 40 objekt-id, uppdelat i ett
# "settings"-block och ett "data"-block 22 steg senare.
CHANNEL_STRIDE = 40
DATA_OFFSET = 22

OFFSET_MIN = 7
OFFSET_MAX = 8
OFFSET_SETPOINT = 11
OFFSET_ROOM_IN_DEMAND = 15  # live status: efterfrågar rummet värme just nu?
OFFSET_RH_LIMIT = 16
OFFSET_FLOOR_LIMIT = 17
OFFSET_TECHNICAL_ALARM = 18
OFFSET_TAMPER = 19
OFFSET_RF_ALARM = 20
OFFSET_BATTERY_ALARM = 21
OFFSET_ACTUAL = 3
OFFSET_NAME = 7
