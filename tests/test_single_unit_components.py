# Copyright (c) 2026 Timothy (TimoPtr)
"""The single-unit register map reads only documented addresses."""

import pytest
from modbus_connection.mock import MockModbusUnit

from intesis_gw_modbus.errors import UnsupportedValueError
from intesis_gw_modbus.single_unit.components import (
    Control,
    Diagnostics,
    Identity,
    Limits,
    Lock,
    Temperatures,
    Window,
)

from .conftest import seed_single_unit

DOCUMENTED = (
    set(range(12))
    | set(range(13, 16))
    | set(range(21, 26))
    | {31, 46}
    | set(range(48, 51))
    | {55, 60, 65, 66, 81, 97, 98}
)


async def test_control_reads_two_documented_blocks(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_single_unit(mock_modbus_unit)
    control = Control(mock_modbus_unit)
    await control.async_update()
    assert [(e.address, e.count) for e in mock_modbus_unit.read_events] == [
        (0, 12),
        (13, 3),
    ]
    assert control.power is True
    assert control.mode == 1
    assert control.setpoint == 215
    assert control.window_timeout == 30


async def test_every_component_reads_only_documented_addresses(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_single_unit(mock_modbus_unit)
    for cls in (Limits, Window, Lock, Identity, Diagnostics, Temperatures):
        mock_modbus_unit.read_events.clear()
        await cls(mock_modbus_unit).async_update()
        covered = {
            address
            for event in mock_modbus_unit.read_events
            for address in range(event.address, event.address + event.count)
        }
        assert covered <= DOCUMENTED, cls.__name__


async def test_init_value_decodes_to_none(mock_modbus_unit: MockModbusUnit) -> None:
    mock_modbus_unit.holding[4] = 0x8000
    mock_modbus_unit.holding[5] = 0x8000
    control = Control(mock_modbus_unit)
    await control.async_update()
    assert control.setpoint is None
    assert control.ambient_temperature is None


async def test_negative_temperature_is_signed(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    mock_modbus_unit.holding[60] = 0xFFF6  # -10 decidegrees
    temps = Temperatures(mock_modbus_unit)
    await temps.async_update()
    assert temps.outdoor_intake == -10


async def test_window_timeout_validator(mock_modbus_unit: MockModbusUnit) -> None:
    control = Control(mock_modbus_unit)
    with pytest.raises(UnsupportedValueError):
        await control.write("window_timeout", 31)
    await control.write("window_timeout", 5)
    assert mock_modbus_unit.holding[13] == 5
