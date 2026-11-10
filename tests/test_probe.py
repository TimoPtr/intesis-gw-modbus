# Copyright (c) 2026 Timothy (TimoPtr)
"""Probing a gateway nobody has identified yet."""

import pytest
from modbus_connection import (
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusTimeoutError,
    ServerDeviceBusyError,
)
from modbus_connection.mock import MockModbusUnit

from intesis_gw_modbus.enums import TemperatureFormat
from intesis_gw_modbus.models import MODELS
from intesis_gw_modbus.probe import GatewayProbe, async_probe_gateway

from .conftest import (
    seed_initialising_single_unit,
    seed_multi_unit,
    seed_single_unit,
)

MHI_SINGLE = MODELS["INMBSMHI001R000"]


async def test_probe_identifies_single_unit_gateway(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_single_unit(mock_modbus_unit)
    assert await async_probe_gateway(mock_modbus_unit) == GatewayProbe(
        device_id=0x0F00,
        model=MHI_SINGLE,
        unsupported_brand=None,
        temperature_format=TemperatureFormat.DECICELSIUS,
        vane_reported=True,
    )


@pytest.mark.parametrize(
    ("raw_setpoint", "expected"),
    [
        (22, TemperatureFormat.CELSIUS),
        (72, TemperatureFormat.FAHRENHEIT),
        (215, TemperatureFormat.DECICELSIUS),
    ],
)
async def test_probe_detects_temperature_format(
    mock_modbus_unit: MockModbusUnit,
    raw_setpoint: int,
    expected: TemperatureFormat,
) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.holding[4] = raw_setpoint
    probe = await async_probe_gateway(mock_modbus_unit)
    assert probe.temperature_format is expected


async def test_probe_of_initialising_gateway(mock_modbus_unit: MockModbusUnit) -> None:
    """The identity is known at once; the format and the vane are not."""
    seed_initialising_single_unit(mock_modbus_unit)
    probe = await async_probe_gateway(mock_modbus_unit)
    assert probe.model is MHI_SINGLE
    assert probe.temperature_format is None
    assert not probe.vane_reported


async def test_probe_names_brand_without_table(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.holding[49] = 0x0801
    probe = await async_probe_gateway(mock_modbus_unit)
    assert probe.device_id == 0x0801
    assert probe.model is None
    assert probe.unsupported_brand == "Daikin"


async def test_probe_of_unknown_device_id(mock_modbus_unit: MockModbusUnit) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.holding[49] = 0x7777
    probe = await async_probe_gateway(mock_modbus_unit)
    assert probe.device_id == 0x7777
    assert probe.model is None
    assert probe.unsupported_brand is None


@pytest.mark.parametrize("error", [IllegalDataAddressError, IllegalFunctionError])
async def test_probe_treats_missing_device_id_as_absent(
    mock_modbus_unit: MockModbusUnit, error: type[Exception]
) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.fail_read(49, error())
    assert await async_probe_gateway(mock_modbus_unit) == GatewayProbe(
        device_id=None,
        model=None,
        unsupported_brand=None,
        temperature_format=None,
        vane_reported=False,
    )


@pytest.mark.parametrize("error", [IllegalDataAddressError, IllegalFunctionError])
async def test_probe_treats_missing_setpoint_and_vane_as_unknown(
    mock_modbus_unit: MockModbusUnit, error: type[Exception]
) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.fail_read(4, error())
    mock_modbus_unit.fail_read(3, error())
    probe = await async_probe_gateway(mock_modbus_unit)
    assert probe.model is MHI_SINGLE
    assert probe.temperature_format is None
    assert not probe.vane_reported


async def test_probe_does_not_read_indoor_unit_registers_as_gateway_data(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """
    On a multi-unit gateway the probed addresses belong to indoor units.

    Register 49 is indoor unit 2's error code there, and 3 and 4 are unit 0's
    setpoint and fan speed, so nothing past the device id may be interpreted.
    """
    seed_multi_unit(mock_modbus_unit, present=(0, 2))
    assert await async_probe_gateway(mock_modbus_unit) == GatewayProbe(
        device_id=0,
        model=None,
        unsupported_brand=None,
        temperature_format=None,
        vane_reported=False,
    )
    assert [event.address for event in mock_modbus_unit.read_events] == [49]


@pytest.mark.parametrize("address", [49, 4, 3])
async def test_probe_propagates_busy(
    mock_modbus_unit: MockModbusUnit, address: int
) -> None:
    """A busy answer says nothing about the register, so the caller retries."""
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.fail_read(address, ServerDeviceBusyError())
    with pytest.raises(ServerDeviceBusyError):
        await async_probe_gateway(mock_modbus_unit)


async def test_probe_propagates_silence(mock_modbus_unit: MockModbusUnit) -> None:
    mock_modbus_unit.fail_requests(ModbusTimeoutError())
    with pytest.raises(ModbusTimeoutError):
        await async_probe_gateway(mock_modbus_unit)


async def test_vane_at_init_value_is_not_reported(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.holding[3] = 0x8000
    probe = await async_probe_gateway(mock_modbus_unit)
    assert not probe.vane_reported
