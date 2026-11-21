"""Modbus 电表集成常量."""
from __future__ import annotations

import logging
from typing import Final
from homeassistant.const import Platform

DOMAIN: Final = "modbus_meter"
LOGGER = logging.getLogger(__package__)

PLATFORMS: Final = [Platform.SENSOR]

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_SLAVE: Final = "slave"
CONF_MODEL: Final = "model"
CONF_NAME: Final = "name"
CONF_POLL_INTERVAL: Final = "poll_interval"

DEFAULT_MODEL: Final = "ddsu666"
DEFAULT_PORT: Final = 8899
DEFAULT_SLAVE: Final = 1
DEFAULT_POLL_INTERVAL: Final = 5
MIN_POLL_INTERVAL: Final = 5