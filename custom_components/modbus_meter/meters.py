"""已支持电表型号的寄存器字典."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

@dataclass(frozen=True)
class MeterRegister:
    """单个数据点：块内寄存器偏移（双寄存器大端 float32）+ 缩放与精度."""
    key: str
    offset: int
    scale: float = 1.0
    decimals: int = 1

@dataclass(frozen=True)
class RegisterBlock:
    """一组连续寄存器及其数据点."""
    address: int
    count: int
    registers: tuple[MeterRegister, ...]

@dataclass(frozen=True)
class MeterProfile:
    """电表型号字典：coordinator 与传感器平台均按此驱动."""
    model: str
    manufacturer: str
    blocks: tuple[RegisterBlock, ...]

DDSU666: Final = MeterProfile(
    model="DDSU666",
    manufacturer="Chint",
    blocks=(
        # 测量区：手册 doc 2000H-2010H（S 视在功率在 V2 手册标保留，旧固件实测有值）
        RegisterBlock(
            address=8193,
            count=16,
            registers=(
                MeterRegister(key="voltage", offset=0),
                MeterRegister(key="current", offset=2, decimals=2),
                MeterRegister(key="power", offset=4, scale=1000.0),
                MeterRegister(key="reactive_power", offset=6, scale=1000.0),
                MeterRegister(key="apparent_power", offset=8, scale=1000.0),
                MeterRegister(key="power_factor", offset=10, decimals=2),
                MeterRegister(key="frequency", offset=14),
            ),
        ),
        # 电能区：正向有功（doc 4000H），单向计量表即总耗电量；
        # doc 400AH 实测与正向同值（固件不区分方向），弃用
        RegisterBlock(
            address=16385,
            count=2,
            registers=(MeterRegister(key="energy", offset=0),),
        ),
    ),
)

METER_PROFILES: Final[dict[str, MeterProfile]] = {
    "ddsu666": DDSU666,
}