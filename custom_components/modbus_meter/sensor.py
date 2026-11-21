"""Modbus 电表传感器平台."""
from __future__ import annotations

from typing import Final
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ModbusMeterConfigEntry
from .coordinator import ModbusMeterCoordinator
from .meters import MeterProfile

# 数据点 key → 传感器呈现元数据（型号间通用，新型号复用或在此扩充）
SENSOR_META: Final = {
    "voltage": (SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, SensorStateClass.MEASUREMENT),
    "current": (SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE, SensorStateClass.MEASUREMENT),
    "power": (SensorDeviceClass.POWER, UnitOfPower.WATT, SensorStateClass.MEASUREMENT),
    "reactive_power": (SensorDeviceClass.REACTIVE_POWER, UnitOfReactivePower.VOLT_AMPERE_REACTIVE, SensorStateClass.MEASUREMENT),
    "apparent_power": (SensorDeviceClass.APPARENT_POWER, UnitOfApparentPower.VOLT_AMPERE, SensorStateClass.MEASUREMENT),
    "power_factor": (SensorDeviceClass.POWER_FACTOR, None, SensorStateClass.MEASUREMENT),
    "frequency": (SensorDeviceClass.FREQUENCY, UnitOfFrequency.HERTZ, SensorStateClass.MEASUREMENT),
    "energy": (SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, SensorStateClass.TOTAL_INCREASING),
}

def _sensor_descriptions(profile: MeterProfile) -> tuple[SensorEntityDescription, ...]:
    """按型号字典生成实体描述表."""
    descriptions = []
    for block in profile.blocks:
        for register in block.registers:
            device_class, unit, state_class = SENSOR_META[register.key]
            descriptions.append(
                SensorEntityDescription(
                    key=register.key,
                    translation_key=register.key,
                    device_class=device_class,
                    native_unit_of_measurement=unit,
                    state_class=state_class,
                )
            )
    return tuple(descriptions)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ModbusMeterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """按型号字典创建全部传感器."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        ModbusMeterSensor(coordinator, entry, description)
        for description in _sensor_descriptions(coordinator.profile)
    )

class ModbusMeterSensor(CoordinatorEntity[ModbusMeterCoordinator], SensorEntity):
    """Modbus 电表传感器."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ModbusMeterCoordinator,
        entry: ModbusMeterConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """初始化实体."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = self.coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """返回协调器数据."""
        return self.coordinator.data.get(self.entity_description.key)