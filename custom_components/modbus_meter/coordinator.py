"""Modbus 电表数据协调器."""
from __future__ import annotations

import struct
from datetime import timedelta
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_NAME,
    CONF_POLL_INTERVAL,
    CONF_SLAVE,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .meters import MeterProfile

def _regs_to_float(regs: list[int]) -> float:
    """两个寄存器按大端 IEEE 754 float32 解码."""
    return struct.unpack(">f", struct.pack(">HH", *regs))[0]

class ModbusMeterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Modbus TCP 轮询电表，按型号字典解码."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AsyncModbusTcpClient,
        entry: ConfigEntry,
        profile: MeterProfile,
    ) -> None:
        """初始化协调器（client 由条目级持有，随卸载关闭）."""
        self.client = client
        self.profile = profile
        self._slave = entry.data[CONF_SLAVE]
        interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        if not self.client.connected and not await self.client.connect():
            raise UpdateFailed("无法建立 Modbus TCP 连接")
        data: dict[str, Any] = {}
        try:
            for block in self.profile.blocks:
                try:
                    result = await self.client.read_holding_registers(
                        address=block.address, count=block.count, device_id=self._slave
                    )
                    if result.isError():
                        raise ModbusException(f"block {block.address}: {result}")
                    for reg in block.registers:
                        value = _regs_to_float(result.registers[reg.offset : reg.offset + 2])
                        data[reg.key] = round(value * reg.scale, reg.decimals)
                except ModbusException as err:
                    # 单块失败降级跳过（如反向电能在部分固件上不存在），不拖垮整表
                    LOGGER.warning("寄存器块 %s 读取失败: %s", block.address, err)
        except ModbusException as err:
            raise UpdateFailed(f"Modbus 通信异常: {err}") from err
        if not data:
            raise UpdateFailed("全部寄存器块读取失败")
        return data

    @property
    def device_info(self) -> DeviceInfo:
        """电表设备信息，全部实体共用（名称由配置流解析落库）."""
        entry = self.config_entry
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer=self.profile.manufacturer,
            model=self.profile.model,
        )