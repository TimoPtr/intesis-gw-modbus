# Copyright (c) 2026 Timothy (TimoPtr)
"""
The raw register map of a multi-unit gateway (INMBSxxxXXXO000).

Each indoor unit ``n`` owns a 20-register block starting at ``n * 20``
(0-based). Offsets 11 and 12 are write-only commands and are written with
``write_register`` directly; the block's readable range still covers them
because the manual says they read back as 0.
"""

from typing import Final

from modbus_connection import ModbusUnit
from modbus_connection.model import Component, boolean, integer

from intesis_gw_modbus.errors import UnsupportedValueError

UNIT_STRIDE: Final = 20
"""Registers per indoor unit block."""

SETPOINT_MIN: Final = 16
SETPOINT_MAX: Final = 30

FILTER_RESET_OFFSET: Final = 11
ERROR_RESET_OFFSET: Final = 12

HW_COMM_STATUS: Final = 2994
ALL_POWER: Final = 2995
ALL_MODE: Final = 2996
ALL_SETPOINT: Final = 2997
ALL_FAN: Final = 2998
ALL_LOCK: Final = 2999


def _celsius_16_30(value: int) -> int:
    if not SETPOINT_MIN <= value <= SETPOINT_MAX:
        raise UnsupportedValueError(f"setpoint {value} is not within 16..30 °C")
    return value


class IndoorUnit(Component):
    """One indoor unit's block, declared at unit 0's addresses."""

    register_ranges = ((0, 13),)

    comm_error = boolean(0)
    power = boolean(1, writable=True)
    mode = integer(2, signed=False, writable=True)
    setpoint = integer(3, signed=False, writable=_celsius_16_30)
    fan_speed = integer(4, signed=False, writable=True)
    remote_control_unlocked = boolean(5, writable=True)
    louver = integer(6, signed=False, writable=True)
    room_temperature = integer(7, signed=False)
    filter_sign = boolean(8)
    error_code = integer(9, signed=False)
    compressor_on = boolean(10)
    thermo_on = boolean(13)

    def __init__(self, unit: ModbusUnit, number: int) -> None:
        """Place the block at indoor unit ``number``'s addresses."""
        super().__init__(unit, base_offset=number * UNIT_STRIDE)
        self.number = number


class GatewayStatus(Component):
    """The gateway's own hardware communication status."""

    register_ranges = ((HW_COMM_STATUS, HW_COMM_STATUS),)

    hw_comm_error = boolean(HW_COMM_STATUS)
