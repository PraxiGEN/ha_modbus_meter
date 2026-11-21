"""Modbus 电表集成入口."""
from __future__ import annotations

from dataclasses import dataclass
from pymodbus.client import AsyncModbusTcpClient
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_HOST, CONF_MODEL, CONF_PORT, DOMAIN, PLATFORMS
from .coordinator import ModbusMeterCoordinator
from .meters import METER_PROFILES

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

@dataclass
class ModbusMeterRuntimeData:
    """条目运行时数据."""
    coordinator: ModbusMeterCoordinator

type ModbusMeterConfigEntry = ConfigEntry[ModbusMeterRuntimeData]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """仅 UI 配置，YAML 无配置项."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ModbusMeterConfigEntry) -> bool:
    """建协调器并首刷，失败自动转入重试."""
    client = AsyncModbusTcpClient(entry.data[CONF_HOST], port=entry.data[CONF_PORT])
    profile = METER_PROFILES[entry.data[CONF_MODEL]]
    coordinator = ModbusMeterCoordinator(hass, client, entry, profile)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = ModbusMeterRuntimeData(coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ModbusMeterConfigEntry) -> bool:
    """卸载平台并关闭 Modbus 连接."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    entry.runtime_data.coordinator.client.close()
    return True