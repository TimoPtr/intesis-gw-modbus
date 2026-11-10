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

from .conftest import seed_initialising_single_unit, seed_single_unit

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
        raw_vane=10,
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
    assert not probe.reports_vane()


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
async def test_probe_treats_missing_registers_as_absent(
    mock_modbus_unit: MockModbusUnit, error: type[Exception]
) -> None:
    """A multi-unit gateway has none of these registers."""
    for address in (49, 4, 3):
        mock_modbus_unit.fail_read(address, error())
    assert await async_probe_gateway(mock_modbus_unit) == GatewayProbe(
        device_id=None,
        model=None,
        unsupported_brand=None,
        temperature_format=None,
        raw_vane=None,
    )


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


async def test_reports_vane(mock_modbus_unit: MockModbusUnit) -> None:
    seed_single_unit(mock_modbus_unit)
    probe = await async_probe_gateway(mock_modbus_unit)
    assert probe.reports_vane()
    mock_modbus_unit.holding[3] = 0x8000
    probe = await async_probe_gateway(mock_modbus_unit)
    assert not probe.reports_vane()


async def test_reports_vane_for_a_model_the_caller_names(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Without a device id the caller says which model's vane codes apply."""
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.fail_read(49, IllegalDataAddressError())
    probe = await async_probe_gateway(mock_modbus_unit)
    assert probe.model is None
    assert not probe.reports_vane()
    assert probe.reports_vane(MHI_SINGLE)
