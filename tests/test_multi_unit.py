# Copyright (c) 2026 Timothy (TimoPtr)
"""The multi-unit gateway device."""

import asyncio
import math

import pytest
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
    ServerDeviceBusyError,
    ServerDeviceFailureError,
)
from modbus_connection.mock import MockModbusUnit, WriteEvent

from intesis_gw_modbus.brands.mhi import MHI
from intesis_gw_modbus.enums import FanSpeed, Mode, VanePosition
from intesis_gw_modbus.errors import NoIndoorUnitsError, UnsupportedValueError
from intesis_gw_modbus.multi_unit.components import IndoorUnit
from intesis_gw_modbus.multi_unit.device import (
    REDISCOVERY_BATCH,
    IntesisMultiUnitGateway,
)

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
    polled = set(range(14)) | set(range(20, 34)) | set(range(140, 154)) | {2994}
    assert polled <= covered
    probed = {e.address // 20 for e in mock_modbus_unit.read_events} - {0, 1, 7, 149}
    assert len(probed) == REDISCOVERY_BATCH
    assert probed.isdisjoint({0, 1, 7})


async def test_setup_reads_each_block_without_crossing(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(127,))
    d = gw(mock_modbus_unit, 128)
    await d.async_update()
    assert sorted(d.indoor_units) == [127]
    assert all(e.count <= 14 for e in mock_modbus_unit.read_events)
    assert len(mock_modbus_unit.read_events) == 130 + REDISCOVERY_BATCH


def _blocks_probed(unit: MockModbusUnit) -> set[int]:
    return {e.address // 20 for e in unit.read_events if e.address < 2994}


async def test_late_unit_is_discovered(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    assert sorted(d.indoor_units) == [0]
    for offset, value in INDOOR_UNIT_BLOCK.items():
        mock_modbus_unit.holding[5 * 20 + offset] = value
    sweeps = -(-47 // REDISCOVERY_BATCH)
    for _ in range(sweeps):
        await d.async_update()
    assert sorted(d.indoor_units) == [0, 5]
    assert d.indoor_units[5].present is True
    assert d.indoor_units[5].mode is Mode.HEAT
    mock_modbus_unit.read_events.clear()
    report = await d.async_update()
    assert report.updated == {"status", "units"}
    assert {0, 5} <= _blocks_probed(mock_modbus_unit)


async def test_rediscovery_sweeps_every_empty_block(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.read_events.clear()
    sweeps = -(-47 // REDISCOVERY_BATCH)
    for _ in range(sweeps):
        await d.async_update()
    assert _blocks_probed(mock_modbus_unit) == set(range(48))
    mock_modbus_unit.read_events.clear()
    await d.async_update()
    assert len(_blocks_probed(mock_modbus_unit) - {0}) == REDISCOVERY_BATCH


async def test_failed_probe_keeps_block_absent(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    for offset, value in INDOOR_UNIT_BLOCK.items():
        mock_modbus_unit.holding[20 + offset] = value
    mock_modbus_unit.fail_read(20, ServerDeviceBusyError())
    sweeps = -(-47 // REDISCOVERY_BATCH)
    for _ in range(sweeps):
        report = await d.async_update()
        assert report.updated == {"status", "units"}
    assert sorted(d.indoor_units) == [0]
    assert 1 in _blocks_probed(mock_modbus_unit)


async def test_probe_propagates_a_dead_link(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.fail_read(20, ModbusConnectionError())

    async def sweep() -> None:
        for _ in range(-(-47 // REDISCOVERY_BATCH)):
            await d.async_update()

    with pytest.raises(ModbusConnectionError):
        await sweep()


async def test_refused_block_means_absent(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 1))
    mock_modbus_unit.fail_read(20, IllegalDataAddressError())
    d = gw(mock_modbus_unit)
    await d.async_update()
    assert sorted(d.indoor_units) == [0]


def _sweeps() -> int:
    return -(-47 // REDISCOVERY_BATCH)


async def test_refused_block_is_probed_again(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 1))
    mock_modbus_unit.fail_read(20, IllegalDataAddressError())
    d = gw(mock_modbus_unit)
    await d.async_update()
    assert sorted(d.indoor_units) == [0]
    mock_modbus_unit.fail_read(20, None)
    for _ in range(_sweeps()):
        await d.async_update()
    assert sorted(d.indoor_units) == [0, 1]


async def test_discoveries_survive_a_dead_link_in_the_same_batch(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    for offset, value in INDOOR_UNIT_BLOCK.items():
        mock_modbus_unit.holding[20 + offset] = value
    mock_modbus_unit.fail_read(40, ModbusConnectionError())

    async def sweep() -> None:
        for _ in range(_sweeps()):
            await d.async_update()

    with pytest.raises(ModbusConnectionError):
        await sweep()
    assert sorted(d.indoor_units) == [0, 1]


async def test_init_sentinel_reads_none_with_healthy_communication(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(3,))
    for offset in (2, 3, 4, 6, 7, 9):
        mock_modbus_unit.holding[60 + offset] = 0x8000
    d = gw(mock_modbus_unit)
    await d.async_update()
    u = d.indoor_units[3]
    assert u.present is True
    assert u.mode is None
    assert u.setpoint is None
    assert u.fan_speed is None
    assert u.vane is None
    assert u.current_temperature is None
    assert u.error is None


async def test_one_failing_block_does_not_take_the_others_down(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 1, 7))
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.holding[23] = 25
    mock_modbus_unit.holding[143] = 26
    mock_modbus_unit.fail_read(0, ServerDeviceFailureError())
    report = await d.async_update()
    assert report.updated == {"status", "units"}
    assert d.indoor_units[0].present is False
    assert d.indoor_units[0].setpoint is None
    assert d.indoor_units[1].present is True
    assert d.indoor_units[1].setpoint == 25
    assert d.indoor_units[7].setpoint == 26
    mock_modbus_unit.fail_read(0, None)
    await d.async_update()
    assert d.indoor_units[0].present is True


async def test_every_block_failing_marks_units_failed(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 1))
    d = gw(mock_modbus_unit)
    await d.async_update()
    notified: list[int] = []
    d.indoor_units[0].component.add_update_listener(lambda: notified.append(0))
    mock_modbus_unit.fail_read(0, ServerDeviceFailureError())
    mock_modbus_unit.fail_read(20, ModbusTimeoutError())
    report = await d.async_update()
    assert report.updated == {"status"}
    assert isinstance(report.failed["units"], ServerDeviceFailureError)
    assert d.indoor_units[0].present is False
    assert d.indoor_units[1].present is False
    assert notified == [0]


async def test_status_timeout_still_polls_units(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.holding[3] = 25
    mock_modbus_unit.fail_read(2994, ModbusTimeoutError())
    report = await d.async_update()
    assert report.updated == {"units"}
    assert isinstance(report.failed["status"], ModbusTimeoutError)
    assert d.indoor_units[0].setpoint == 25
    assert d.hw_comm_ok is True  # last good reading kept


async def test_saved_indoor_units_reference_sees_new_units(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    saved = d.indoor_units
    for offset, value in INDOOR_UNIT_BLOCK.items():
        mock_modbus_unit.holding[5 * 20 + offset] = value
    for _ in range(_sweeps()):
        await d.async_update()
    assert saved is d.indoor_units
    assert list(saved) == [0, 5]


async def test_discovery_clears_units_failure(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.fail_read(0, ServerDeviceFailureError())
    for offset, value in INDOOR_UNIT_BLOCK.items():
        mock_modbus_unit.holding[20 + offset] = value
    report = None
    for _ in range(_sweeps()):
        report = await d.async_update()
        if 1 in d.indoor_units:
            break
    assert report is not None
    assert "units" in report.updated
    assert "units" not in report.failed


async def test_dead_link_marks_known_units_unreachable(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 1))
    d = gw(mock_modbus_unit)
    await d.async_update()
    notified: list[int] = []
    d.indoor_units[1].component.add_update_listener(lambda: notified.append(1))
    mock_modbus_unit.fail_read(2994, ModbusConnectionError())
    with pytest.raises(ModbusConnectionError):
        await d.async_update()
    assert d.indoor_units[0].present is False
    assert d.indoor_units[1].present is False
    assert notified == [1]
    mock_modbus_unit.fail_read(2994, None)
    await d.async_update()
    assert d.indoor_units[0].present is True


async def test_cancelled_probe_keeps_block_queued(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    for offset, value in INDOOR_UNIT_BLOCK.items():
        mock_modbus_unit.holding[20 + offset] = value
    mock_modbus_unit.fail_read(20, asyncio.CancelledError())  # type: ignore[arg-type]

    async def sweep() -> None:
        for _ in range(_sweeps()):
            await d.async_update()

    with pytest.raises(asyncio.CancelledError):
        await sweep()
    mock_modbus_unit.fail_read(20, None)
    await sweep()
    assert 1 in d.indoor_units


async def test_overlapping_updates_do_not_drop_blocks(
    mock_modbus_unit: MockModbusUnit, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    original = IndoorUnit.async_update

    async def slow_update(self: IndoorUnit, *, notify: bool = True) -> None:
        await asyncio.sleep(0)  # let the other update run, like real bus I/O
        await original(self, notify=notify)

    monkeypatch.setattr(IndoorUnit, "async_update", slow_update)
    for _ in range(_sweeps()):
        await asyncio.gather(d.async_update(), d.async_update())
    queued = sorted(c.number for c in d._empty)
    assert queued == list(range(1, 48))


async def test_silent_gateway_notifies_before_raising(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    notified: list[int] = []
    d.indoor_units[0].component.add_update_listener(lambda: notified.append(0))
    mock_modbus_unit.fail_requests(ModbusTimeoutError())
    with pytest.raises(ModbusTimeoutError):
        await d.async_update()
    assert d.indoor_units[0].present is False
    assert notified == [0]


async def test_silent_gateway_gives_up_after_two_timeouts(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 1, 2, 3, 7))
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.read_events.clear()
    mock_modbus_unit.fail_requests(ModbusTimeoutError())
    with pytest.raises(ModbusTimeoutError):
        await d.async_update()
    assert len(mock_modbus_unit.read_events) == 2  # the status, then one unit
    assert not any(view.present for view in d.indoor_units.values())


async def test_link_dying_mid_poll_spares_the_remaining_reads(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 1, 2, 3, 7))
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.read_events.clear()
    mock_modbus_unit.fail_read(20, ModbusTimeoutError())
    mock_modbus_unit.fail_read(40, ModbusTimeoutError())
    report = await d.async_update()
    assert report.updated == {"status", "units"}
    assert [e.address for e in mock_modbus_unit.read_events] == [2994, 0, 20, 40]
    assert d.indoor_units[0].present is True
    assert not any(d.indoor_units[n].present for n in (1, 2, 3, 7))


async def test_isolated_timeout_does_not_stop_the_poll(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0, 1, 2))
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.fail_read(20, ModbusTimeoutError())
    report = await d.async_update()
    assert report.updated == {"status", "units"}
    assert d.indoor_units[0].present is True
    assert d.indoor_units[1].present is False
    assert d.indoor_units[2].present is True


async def test_probe_timeout_ends_rediscovery_for_this_poll(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    head = d._empty[0].number
    mock_modbus_unit.fail_read(head * 20, ModbusTimeoutError())
    mock_modbus_unit.read_events.clear()
    await d.async_update()
    assert [e.address for e in mock_modbus_unit.read_events] == [2994, 0, head * 20]
    mock_modbus_unit.fail_read(head * 20, None)
    for _ in range(_sweeps()):
        await d.async_update()
    assert sorted(c.number for c in d._empty) == list(range(1, 48))


async def test_silent_gateway_raises_timeout(mock_modbus_unit: MockModbusUnit) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.fail_read(2994, ModbusTimeoutError())
    mock_modbus_unit.fail_read(0, ModbusTimeoutError())
    with pytest.raises(ModbusTimeoutError):
        await d.async_update()


async def test_dead_link_while_polling_units_raises(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed_multi_unit(mock_modbus_unit, present=(0,))
    d = gw(mock_modbus_unit)
    await d.async_update()
    mock_modbus_unit.fail_read(0, ModbusConnectionError())
    with pytest.raises(ModbusConnectionError):
        await d.async_update()


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
        await u.async_set_setpoint(math.nan)
    with pytest.raises(UnsupportedValueError):
        await u.async_set_setpoint(math.inf)
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
