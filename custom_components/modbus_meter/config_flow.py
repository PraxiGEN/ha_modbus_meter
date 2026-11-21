"""Modbus 电表配置流."""
from __future__ import annotations

from typing import Any
import voluptuous as vol
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_SLAVE,
    DEFAULT_MODEL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
    DOMAIN,
    MIN_POLL_INTERVAL,
)
from .meters import METER_PROFILES

MODEL_OPTIONS = [
    SelectOptionDict(value=key, label=profile.model)
    for key, profile in METER_PROFILES.items()
]

async def _async_test_connection(host: str, port: int, slave: int, probe_address: int) -> bool:
    """连接并试探读一个寄存器，验证地址与从机号."""
    client = AsyncModbusTcpClient(host, port=port)
    try:
        if not await client.connect():
            return False
        result = await client.read_holding_registers(
            address=probe_address, count=1, device_id=slave
        )
        return not result.isError()
    except ModbusException:
        return False
    finally:
        client.close()

class ModbusMeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """处理集成配置流."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ModbusMeterOptionsFlowHandler:
        """挂载 options flow."""
        return ModbusMeterOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """第一级：选择电表型号."""
        if user_input is not None:
            self._model: str = user_input[CONF_MODEL]
            return await self.async_step_connection()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL, default=DEFAULT_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=MODEL_OPTIONS, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """第二级：连接参数（型号已定，名称预填随之确定）."""
        profile = METER_PROFILES[self._model]
        errors: dict[str, str] = {}
        if user_input is not None:
            # NumberSelector 返回 float，pymodbus 的 device_id 只认 int，入口归一化
            port = int(user_input[CONF_PORT])
            slave = int(user_input[CONF_SLAVE])
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: port,
                    CONF_SLAVE: slave,
                }
            )
            # 设备名链：用户填写 > 型号；与已有设备名重名（多表未改名）则追加从机号
            name = user_input.get(CONF_NAME, "").strip() or profile.model
            if any(
                e.data.get(CONF_NAME) == name for e in self._async_current_entries()
            ):
                name = f"{profile.model} #{slave}"
            if await _async_test_connection(
                user_input[CONF_HOST], port, slave, profile.blocks[0].address
            ):
                # 条目标题标识连接（host:端口），设备名走 CONF_NAME
                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]}:{port}",
                    data={
                        CONF_MODEL: self._model,
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: port,
                        CONF_SLAVE: slave,
                        CONF_NAME: name,
                    },
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="connection",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=profile.model): TextSelector(),
                    vol.Required(CONF_HOST): TextSelector(),
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
                        NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
                    ),
                    vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): NumberSelector(
                        NumberSelectorConfig(min=1, max=247, step=1, mode="box")
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """重新配置第一步：确认型号."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            self._model = user_input[CONF_MODEL]
            return await self.async_step_reconfigure_connection()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL, default=entry.data[CONF_MODEL]
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=MODEL_OPTIONS, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_reconfigure_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """重新配置第二步：连接参数（预填当前值）."""
        entry = self._get_reconfigure_entry()
        profile = METER_PROFILES[self._model]
        errors: dict[str, str] = {}
        if user_input is not None:
            port = int(user_input[CONF_PORT])
            slave = int(user_input[CONF_SLAVE])
            name = user_input.get(CONF_NAME, "").strip() or profile.model
            if any(
                e.data.get(CONF_NAME) == name
                for e in self._async_current_entries()
                if e.entry_id != entry.entry_id
            ):
                name = f"{profile.model} #{slave}"
            if await _async_test_connection(
                user_input[CONF_HOST], port, slave, profile.blocks[0].address
            ):
                return self.async_update_reload_and_abort(
                    entry,
                    title=f"{user_input[CONF_HOST]}:{port}",
                    data={
                        CONF_MODEL: self._model,
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: port,
                        CONF_SLAVE: slave,
                        CONF_NAME: name,
                    },
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="reconfigure_connection",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME, default=entry.data.get(CONF_NAME, profile.model)
                    ): TextSelector(),
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): TextSelector(),
                    vol.Required(
                        CONF_PORT, default=entry.data[CONF_PORT]
                    ): NumberSelector(
                        NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
                    ),
                    vol.Required(
                        CONF_SLAVE, default=entry.data[CONF_SLAVE]
                    ): NumberSelector(
                        NumberSelectorConfig(min=1, max=247, step=1, mode="box")
                    ),
                }
            ),
            errors=errors,
        )

class ModbusMeterOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """运行参数配置（保存后自动重载条目生效）."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """轮询间隔设置."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_POLL_INTERVAL, max=3600, step=1, mode="box"
                        )
                    ),
                }
            ),
        )