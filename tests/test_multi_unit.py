# Copyright (c) 2026 Timothy (TimoPtr)
"""The multi-unit gateway device."""

import pytest
from modbus_connection import IllegalDataAddressError, ServerDeviceBusyError
from modbus_connection.mock import MockModbusUnit, WriteEvent

from intesis_gw_modbus.brands.mhi import MHI
from intesis_gw_modbus.enums import FanSpeed, Mode, VanePosition
from intesis_gw_modbus.errors import NoIndoorUnitsError, UnsupportedValueError
from intesis_gw_modbus.multi_unit.device import IntesisMultiUnitGateway

from .conftest import INDOOR_UNIT_BLOCK, seed_multi_unit


def gw(unit: MockModbusUnit, count: int = 48) -> IntesisMultiUnitGateway:
    return IntesisMultiUnitGateway(unit, brand=MHI, unit_count=count)


async def test_only_present_units_are_polled(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 1, 7))
    d = gw(mock_modbus_unit)
    await d.async_update()
    assert sorted(d.indoor_units) == [0, 1, 7]
    mock_modbus_unit.read_events.clear()
    report = await d.async_update()
    assert report.updated == {"status", "units"}
    covered = {
        address
        for event in mock_modbus_unit.read_events
        for address in range(event.address, event.address + event.count)
    }
    assert covered == (
        set(range(14)) | set(range(20, 34)) | set(range(140, 154)) | {2994}
    )


async def test_setup_reads_each_block_without_crossing(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(127,))
    d = gw(mock_modbus_unit, 128)
    await d.async_update()
    assert sorted(d.indoor_units) == [127]
    assert all(e.count <= 14 for e in mock_modbus_unit.read_events)
    assert len(mock_modbus_unit.read_events) == 130  # 128 probes + status + unit


async def test_refused_block_means_absent(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 1))
    mock_modbus_unit.fail_read(20, IllegalDataAddressError())
    d = gw(mock_modbus_unit)
    await d.async_update()
    assert sorted(d.indoor_units) == [0]


async def test_indoor_unit_view(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(3,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    u = d.indoor_units[3]
    assert u.number == 3
    assert u.present is True
    assert u.power is True
    assert u.mode is Mode.HEAT
    assert u.setpoint == 22.0
    assert u.fan_speed is FanSpeed.MEDIUM
    assert u.vane is VanePosition.SWING
    assert u.current_temperature == 21.0
    assert u.remote_control_locked is False
    assert u.filter_sign is False
    assert u.compressor_on is True
    assert u.thermo_on is True
    assert u.error is not None
    assert u.error.code == 0
    assert u.setpoint_min == 16.0
    assert u.setpoint_max == 30.0
    assert u.setpoint_step == 1.0
    assert u.available_modes == (Mode.COOL, Mode.HEAT, Mode.FAN, Mode.AUTO, Mode.DRY)
    assert u.available_fan_speeds == (
        FanSpeed.LOW,
        FanSpeed.MEDIUM,
        FanSpeed.HIGH,
        FanSpeed.POWERFUL,
    )
    assert u.available_vane_positions == (
        VanePosition.SWING,
        VanePosition.POSITION_1,
        VanePosition.POSITION_2,
        VanePosition.POSITION_3,
        VanePosition.POSITION_4,
    )
    assert d.hw_comm_ok is True


async def test_indoor_unit_writes(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(3,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    u = d.indoor_units[3]
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)
    await u.async_set_power(False)
    await u.async_set_mode(Mode.COOL)
    await u.async_set_setpoint(24)
    await u.async_set_fan_speed(FanSpeed.HIGH)
    await u.async_set_vane(VanePosition.POSITION_4)
    await u.async_set_remote_control_locked(True)
    await u.async_reset_filter()
    await u.async_reset_error()
    assert [(w.address, w.values[0]) for w in writes] == [
        (61, 0),
        (62, 0),
        (63, 24),
        (64, 2),
        (66, 4),
        (65, 0),
        (71, 1),
        (72, 1),
    ]
    with pytest.raises(UnsupportedValueError):
        await u.async_set_setpoint(22.5)
    with pytest.raises(UnsupportedValueError):
        await u.async_set_setpoint(31)
    with pytest.raises(UnsupportedValueError):
        await u.async_set_fan_speed(FanSpeed.AUTO)


async def test_unit_that_drops_out_reads_none(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(3,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.holding[60] = 1  # communication error, block otherwise intact
    await d.async_update()
    u = d.indoor_units[3]
    assert u.present is False
    assert u.power is None
    assert u.mode is None
    assert u.fan_speed is None
    assert u.vane is None
    assert u.setpoint is None
    assert u.current_temperature is None
    assert u.error is None
    assert u.filter_sign is None
    assert u.compressor_on is None
    assert u.thermo_on is None
    assert u.remote_control_locked is None


async def test_all_units_commands(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)
    await d.async_set_all_power(True)
    await d.async_set_all_mode(Mode.DRY)
    await d.async_set_all_setpoint(20)
    await d.async_set_all_fan_speed(FanSpeed.LOW)
    await d.async_set_all_remote_control_locked(False)
    assert [(w.address, w.values[0]) for w in writes] == [
        (2995, 1),
        (2996, 4),
        (2997, 20),
        (2998, 0),
        (2999, 1),
    ]
    with pytest.raises(UnsupportedValueError):
        await d.async_set_all_setpoint(15)


async def test_timing_requested(mock_modbus_unit: MockModbusUnit) -> None:
    gw(mock_modbus_unit)
    assert mock_modbus_unit.required_timeout == 3.0


async def test_hw_comm_error(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    mock_modbus_unit.holding[2994] = 1
    d = gw(mock_modbus_unit)
    await d.async_update()
    assert d.hw_comm_ok is False


async def test_field_validator_guards_direct_writes(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(3,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    with pytest.raises(UnsupportedValueError):
        await d.indoor_units[3].component.write("setpoint", 31)


async def test_read_raw_covers_status_and_units(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 7))
    d = gw(mock_modbus_unit)
    raw = await d.async_read_raw()
    assert raw["holding"][2994] == 0
    assert raw["holding"][143] == 22
    assert 20 not in raw["holding"]


async def test_busy_reply_during_setup_is_not_absence(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 1))
    mock_modbus_unit.fail_read(20, ServerDeviceBusyError())
    d = gw(mock_modbus_unit)
    with pytest.raises(ServerDeviceBusyError):
        await d.async_update()
    mock_modbus_unit.fail_read(20, None)
    await d.async_update()
    assert sorted(d.indoor_units) == [0, 1]


async def test_no_units_at_setup_is_retried(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=())
    d = gw(mock_modbus_unit)
    with pytest.raises(NoIndoorUnitsError):
        await d.async_update()
    for offset, value in INDOOR_UNIT_BLOCK.items():
        mock_modbus_unit.holding[40 + offset] = value
    await d.async_update()
    assert sorted(d.indoor_units) == [2]
