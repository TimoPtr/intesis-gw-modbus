# Copyright (c) 2026 Timothy (TimoPtr)
"""Enum values are stable lower-case names."""

from intesis_gw_modbus.enums import FanSpeed, Mode, VanePosition


def test_enum_values_are_lowercase_names() -> None:
    assert Mode.FAN.value == "fan"
    assert FanSpeed.POWERFUL.value == "powerful"
    assert VanePosition.POSITION_3.value == "position_3"
