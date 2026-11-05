# Copyright (c) 2026 Timothy (TimoPtr)
"""The AirConditioner protocol names the shared surface."""

from typing import get_type_hints

from intesis_gw_modbus.ac import AirConditioner


def test_protocol_lists_the_shared_commands() -> None:
    assert {"async_set_power", "async_set_mode", "async_set_setpoint"} <= set(
        dir(AirConditioner)
    )
    assert "power" in dir(AirConditioner)
    assert get_type_hints(AirConditioner.async_set_mode)["mode"].__name__ == "Mode"
