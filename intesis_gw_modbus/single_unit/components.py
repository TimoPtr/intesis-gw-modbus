# Copyright (c) 2026 Timothy (TimoPtr)
"""
The raw register map of a single-unit gateway (INMBSxxx001R000).

Addresses are 0-based protocol addresses from the manual. Each component's
``register_ranges`` lists only documented addresses: the gateway refuses a
block read that touches an undefined one. Values are raw integers; the device
layer applies the brand's code maps and the temperature format.
"""

from modbus_connection.model import Component, boolean, integer, raw_register

from intesis_gw_modbus.errors import UnsupportedValueError
from intesis_gw_modbus.temperature import INIT_VALUE

MAX_WINDOW_TIMEOUT_MINUTES = 30


def _minutes_0_30(value: int) -> int:
    if not 0 <= value <= MAX_WINDOW_TIMEOUT_MINUTES:
        raise UnsupportedValueError(
            f"window timeout {value} is not within 0..30 minutes"
        )
    return value


class Control(Component):
    """Registers 0..15: what the unit does and the gateway's own settings."""

    register_ranges = ((0, 11), (13, 15))

    power = boolean(0, nan=INIT_VALUE, writable=True)
    mode = integer(1, signed=False, nan=INIT_VALUE, writable=True)
    fan_speed = integer(2, signed=False, nan=INIT_VALUE, writable=True)
    vane = integer(3, signed=False, nan=INIT_VALUE, writable=True)
    setpoint = integer(4, nan=INIT_VALUE, writable=True)
    ambient_temperature = integer(5, nan=INIT_VALUE)
    window_contact = boolean(6, writable=True)
    gateway_disabled = boolean(7, writable=True)
    remote_control_disabled = boolean(8, writable=True)
    operation_hours = integer(9, signed=False)
    alarm = boolean(10)
    error_code = integer(11, signed=False)
    window_timeout = integer(13, signed=False, writable=_minutes_0_30)
    baudrate_code = integer(14, signed=False)
    slave_address = integer(15, signed=False)


class Limits(Component):
    """Registers 21..25: fan speed count, external reference, setpoint limits."""

    register_ranges = ((21, 25),)

    max_fan_speeds = integer(21, signed=False, nan=INIT_VALUE)
    external_temperature = integer(22, nan=INIT_VALUE, writable=True)
    real_setpoint = integer(23, nan=INIT_VALUE)
    setpoint_max = integer(24, nan=INIT_VALUE)
    setpoint_min = integer(25, nan=INIT_VALUE)


class Window(Component):
    """Register 31: open-window status."""

    register_ranges = ((31, 31),)

    window_open = boolean(31)


class Lock(Component):
    """Register 46: Center/Remote lock state."""

    register_ranges = ((46, 46),)

    control_lock = integer(46, signed=False, nan=INIT_VALUE)


class Identity(Component):
    """Registers 48..50: switch value, device id, software version."""

    register_ranges = ((48, 50),)

    switch_value = raw_register(48)
    device_id = raw_register(49)
    software_version = raw_register(50)


class Diagnostics(Component):
    """Registers 55, 81, 97, 98: counters and gateway behaviour switches."""

    register_ranges = ((55, 55), (81, 81), (97, 98))

    undervoltage_hours = integer(55, signed=False)
    error_address = integer(81, signed=False)
    block_periodic_sendings = boolean(97, writable=True)
    is_master = boolean(98, writable=True)


class Temperatures(Component):
    """Registers 60, 65, 66: the extra temperatures the unit reports."""

    register_ranges = ((60, 60), (65, 66))

    outdoor_intake = integer(60, nan=INIT_VALUE)
    input_reference = integer(65, nan=INIT_VALUE)
    return_path = integer(66, nan=INIT_VALUE)
