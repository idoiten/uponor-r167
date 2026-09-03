"""Constants for the Uponor R-167 integration."""

DOMAIN = "uponor_r167"

CONF_MAX_CHANNELS = "max_channels"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_MAX_CHANNELS = 30
DEFAULT_SCAN_INTERVAL = 60  # seconds

# Fixed layout: each channel occupies 40 object ids, split into a
# "settings" block and a "data" block 22 steps later.
CHANNEL_STRIDE = 40
DATA_OFFSET = 22

OFFSET_MIN = 7
OFFSET_MAX = 8
OFFSET_SETPOINT = 11
OFFSET_ROOM_IN_DEMAND = 15  # live status: is the room currently calling for heat?
OFFSET_RH_LIMIT = 16
OFFSET_FLOOR_LIMIT = 17
OFFSET_TECHNICAL_ALARM = 18
OFFSET_TAMPER = 19
OFFSET_RF_ALARM = 20
OFFSET_BATTERY_ALARM = 21
OFFSET_ACTUAL = 3
OFFSET_NAME = 7

# System-wide temperature values (not tied to a specific room).
OUTDOOR_TEMP_ID = 67
AVG_INDOOR_TEMP_ID = 37
