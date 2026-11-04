# Copyright (c) 2026 Timothy (TimoPtr)
"""The single-unit gateway device: typed readings, writes, failure handling."""

import pytest
from modbus_connection import IllegalDataAddressError, ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit, WriteEvent

from intesis_gw_modbus.brands.mhi import MHI
from intesis_gw_modbus.enums import (
    ControlLock,
    ErrorState,
    FanSpeed,
    Mode,
    TemperatureFormat,
    VanePosition,
)
from intesis_gw_modbus.errors import (
    ErrorInfo,
    UnsupportedValueError,
    WrongGatewayError,
)
from intesis_gw_modbus.single_unit.device import (
    READINGS,
    SETTINGS,
    IntesisSingleUnitGateway,
)

from .conftest import seed_initialising_single_unit, seed_single_unit


def gw(unit: MockModbusUnit) -> IntesisSingleUnitGateway:
    return IntesisSingleUnitGateway(
        unit, brand=MHI, temperature_format=TemperatureFormat.DECICELSIUS
    )


async def test_setup_validates_device_id(mock_modbus_unit: MockModbusUnit) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.holding[49] = 0x0801
    with pytest.raises(WrongGatewayError):
        await gw(mock_modbus_unit).async_update()


async def test_timing_requested(mock_modbus_unit: MockModbusUnit) -> None:
    gw(mock_modbus_unit)
    assert mock_modbus_unit.required_timeout == 3.0
    assert mock_modbus_unit.message_spacing == 0.02


async def test_typed_readings(mock_modbus_unit: MockModbusUnit) -> None:
    seed_single_unit(mock_modbus_unit)
    d = gw(mock_modbus_unit)
    report = await d.async_update()
    assert report.updated == set(READINGS) | set(SETTINGS)
    assert not report.failed
    assert d.power is True
    assert d.mode is Mode.HEAT
    assert d.fan_speed is FanSpeed.MEDIUM
    assert d.vane is VanePosition.SWING
    assert d.setpoint == 21.5
    assert d.current_temperature == 20.3
    assert d.real_setpoint == 21.5
    assert d.setpoint_min == 16.0
    assert d.setpoint_max == 30.0
    assert d.setpoint_step == 0.5
    assert d.available_modes == (Mode.AUTO, Mode.HEAT, Mode.DRY, Mode.FAN, Mode.COOL)
    assert d.available_fan_speeds == (
        FanSpeed.AUTO,
        FanSpeed.LOW,
        FanSpeed.MEDIUM,
        FanSpeed.HIGH,
        FanSpeed.POWERFUL,
    )
    assert d.available_vane_positions == (
        VanePosition.POSITION_1,
        VanePosition.POSITION_2,
        VanePosition.POSITION_3,
        VanePosition.POSITION_4,
        VanePosition.SWING,
    )
    assert d.external_temperature is None
    assert d.outdoor_intake_temperature == 12.5
    assert d.input_reference_temperature is None
    assert d.return_path_temperature == 24.0
    assert d.error == ErrorInfo(0, ErrorState.NONE, None, None)
    assert d.alarm is False
    assert d.window_open is False
    assert d.window_contact is False
    assert d.window_timeout_minutes == 30
    assert d.gateway_disabled is False
    assert d.remote_control_disabled is False
    assert d.block_periodic_sendings is False
    assert d.is_master is False
    assert d.control_lock is ControlLock.REMOTE_UNLOCK
    assert d.operation_hours == 1234
    assert d.undervoltage_hours == 3
    assert d.error_address == 0
    assert d.max_fan_speeds == 4
    assert d.device_id == 0x0F00
    assert d.software_version == "20"
    assert d.detected_temperature_format is TemperatureFormat.DECICELSIUS


async def test_initialising_gateway_reads_none(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_initialising_single_unit(mock_modbus_unit)
    d = gw(mock_modbus_unit)
    await d.async_update()
    assert d.power is None
    assert d.mode is None
    assert d.fan_speed is None
    assert d.vane is None
    assert d.setpoint is None
    assert d.current_temperature is None
    assert d.control_lock is None
    assert d.setpoint_min == 16.0
    assert d.setpoint_max == 30.0
    assert d.available_fan_speeds == (
        FanSpeed.AUTO,
        FanSpeed.LOW,
        FanSpeed.MEDIUM,
        FanSpeed.HIGH,
    )
    assert d.error is not None
    assert d.error.state is ErrorState.INITIALISING
    assert d.detected_temperature_format is None


async def test_celsius_and_fahrenheit_formats(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.holding[4] = 72
    mock_modbus_unit.holding[5] = 70
    mock_modbus_unit.holding[24] = 86
    mock_modbus_unit.holding[25] = 61
    d = IntesisSingleUnitGateway(
        mock_modbus_unit, brand=MHI, temperature_format=TemperatureFormat.FAHRENHEIT
    )
    await d.async_update()
    assert d.setpoint == 22.2
    assert d.current_temperature == 21.1
    assert d.setpoint_step == 1.0
    await d.async_set_setpoint(23.0)
    assert mock_modbus_unit.holding[4] == 73


async def test_writes_land_on_the_right_registers(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_single_unit(mock_modbus_unit)
    d = gw(mock_modbus_unit)
    await d.async_update()
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)
    await d.async_set_power(False)
    await d.async_set_mode(Mode.COOL)
    await d.async_set_fan_speed(FanSpeed.POWERFUL)
    await d.async_set_vane(VanePosition.POSITION_2)
    await d.async_set_setpoint(24.5)
    await d.async_set_external_temperature(21.3)
    await d.async_set_external_temperature(None)
    await d.async_set_window_contact(True)
    await d.async_set_window_timeout(5)
    await d.async_set_remote_control_disabled(True)
    await d.async_set_gateway_disabled(True)
    await d.async_set_block_periodic_sendings(True)
    await d.async_set_master(True)
    await d.async_reset_error()
    await d.async_reset_gateway()
    assert [(w.address, w.values[0], w.function_code) for w in writes] == [
        (0, 0, 6),
        (1, 4, 6),
        (2, 4, 6),
        (3, 2, 6),
        (4, 245, 6),
        (22, 213, 6),
        (22, 0x8000, 6),
        (6, 1, 6),
        (13, 5, 6),
        (8, 1, 6),
        (7, 1, 6),
        (97, 1, 6),
        (98, 1, 6),
        (45, 1, 6),
        (99, 1, 6),
    ]


async def test_set_fan_speed_rejects_unavailable_speed(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.holding[21] = 3
    d = gw(mock_modbus_unit)
    await d.async_update()
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)
    with pytest.raises(UnsupportedValueError):
        await d.async_set_fan_speed(FanSpeed.POWERFUL)
    assert writes == []


async def test_set_setpoint_outside_limits_rejected(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_single_unit(mock_modbus_unit)
    d = gw(mock_modbus_unit)
    await d.async_update()
    with pytest.raises(UnsupportedValueError):
        await d.async_set_setpoint(31.0)
    with pytest.raises(UnsupportedValueError):
        await d.async_set_setpoint(15.5)


async def test_set_mode_and_vane_reject_unmapped(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_single_unit(mock_modbus_unit)
    d = IntesisSingleUnitGateway(
        mock_modbus_unit,
        brand=MHI,
        temperature_format=TemperatureFormat.DECICELSIUS,
    )
    await d.async_update()
    brand_without_dry = MHI.__class__(
        **{
            **MHI.__dict__,
            "modes": {0: Mode.AUTO},
            "vane_positions": {10: VanePosition.SWING},
        }
    )
    d = IntesisSingleUnitGateway(
        mock_modbus_unit,
        brand=brand_without_dry,
        temperature_format=TemperatureFormat.DECICELSIUS,
    )
    await d.async_update()
    with pytest.raises(UnsupportedValueError):
        await d.async_set_mode(Mode.DRY)
    with pytest.raises(UnsupportedValueError):
        await d.async_set_vane(VanePosition.POSITION_1)


async def test_unknown_enum_code_reads_none(mock_modbus_unit: MockModbusUnit) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.holding[1] = 9
    mock_modbus_unit.holding[2] = 9
    mock_modbus_unit.holding[3] = 9
    mock_modbus_unit.holding[46] = 9
    d = gw(mock_modbus_unit)
    await d.async_update()
    assert d.mode is None
    assert d.fan_speed is None
    assert d.vane is None
    assert d.control_lock is None


async def test_failed_block_lands_in_report(mock_modbus_unit: MockModbusUnit) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.fail_read(60, IllegalDataAddressError())
    d = gw(mock_modbus_unit)
    report = await d.async_update()
    assert "temperatures" in report.failed
    assert "control" in report.updated
    assert d.outdoor_intake_temperature is None


async def test_split_updates(mock_modbus_unit: MockModbusUnit) -> None:
    seed_single_unit(mock_modbus_unit)
    d = gw(mock_modbus_unit)
    assert (await d.async_update_readings()).updated == set(READINGS)
    assert (await d.async_update_settings()).updated == set(SETTINGS)


async def test_dead_device_raises(mock_modbus_unit: MockModbusUnit) -> None:
    seed_single_unit(mock_modbus_unit)
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.fail_requests(ModbusTimeoutError())
    with pytest.raises(ModbusTimeoutError):
        await d.async_update()


async def test_read_raw_covers_all(mock_modbus_unit: MockModbusUnit) -> None:
    seed_single_unit(mock_modbus_unit)
    d = gw(mock_modbus_unit)
    raw = await d.async_read_raw()
    assert raw["holding"][49] == 0x0F00
    assert 12 not in raw["holding"]
    assert 47 not in raw["holding"]


async def test_initialising_gateway_reads_none_everywhere(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_initialising_single_unit(mock_modbus_unit)
    d = gw(mock_modbus_unit)
    await d.async_update()
    for name in (
        "window_contact",
        "gateway_disabled",
        "remote_control_disabled",
        "operation_hours",
        "alarm",
        "window_open",
        "window_timeout_minutes",
        "undervoltage_hours",
        "error_address",
        "block_periodic_sendings",
        "is_master",
        "real_setpoint",
        "external_temperature",
        "outdoor_intake_temperature",
        "input_reference_temperature",
        "return_path_temperature",
        "max_fan_speeds",
    ):
        assert getattr(d, name) is None, name


async def test_initialising_gateway_does_not_warn(
    mock_modbus_unit: MockModbusUnit, caplog: pytest.LogCaptureFixture
) -> None:
    seed_initialising_single_unit(mock_modbus_unit)
    await gw(mock_modbus_unit).async_update()
    assert "no mapping" not in caplog.text


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, (FanSpeed.AUTO, FanSpeed.HIGH)),
        (2, (FanSpeed.AUTO, FanSpeed.LOW, FanSpeed.HIGH)),
        (3, (FanSpeed.AUTO, FanSpeed.LOW, FanSpeed.MEDIUM, FanSpeed.HIGH)),
    ],
)
async def test_fan_speed_sets_follow_register_21(
    mock_modbus_unit: MockModbusUnit, count: int, expected: tuple[FanSpeed, ...]
) -> None:
    seed_single_unit(mock_modbus_unit)
    mock_modbus_unit.holding[21] = count
    mock_modbus_unit.holding[2] = count  # the top speed's code on this unit
    d = gw(mock_modbus_unit)
    await d.async_update()
    assert d.available_fan_speeds == expected
    assert d.fan_speed is FanSpeed.HIGH
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)
    await d.async_set_fan_speed(FanSpeed.HIGH)
    assert [(w.address, w.values[0]) for w in writes] == [(2, count)]
