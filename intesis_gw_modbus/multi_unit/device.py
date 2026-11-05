# Copyright (c) 2026 Timothy (TimoPtr)
"""The multi-unit gateway as a typed device, one view per indoor unit."""

import asyncio
import math
from collections import deque
from collections.abc import Iterable, Mapping
from typing import Final

from modbus_connection import (
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusConnectionError,
    ModbusError,
    ModbusTimeoutError,
    ModbusUnit,
)
from modbus_connection.model import ComponentGroup, Device, Raw, UpdateReport

from intesis_gw_modbus.brands.base import BrandTable
from intesis_gw_modbus.enums import FanSpeed, Mode, VanePosition
from intesis_gw_modbus.errors import (
    ErrorInfo,
    NoIndoorUnitsError,
    UnsupportedValueError,
    decode_error,
)

from .components import (
    ALL_FAN,
    ALL_LOCK,
    ALL_MODE,
    ALL_POWER,
    ALL_SETPOINT,
    ERROR_RESET_OFFSET,
    FILTER_RESET_OFFSET,
    SETPOINT_MAX,
    SETPOINT_MIN,
    UNIT_STRIDE,
    GatewayStatus,
    IndoorUnit,
)

POLLED: Final = ("status", "units")

REDISCOVERY_BATCH: Final = 8
"""Empty blocks re-probed after each poll, round-robin, so late units appear."""

_REQUIRED_TIMEOUT: Final = 3.0

_SILENCE_BUDGET: Final = 2
"""Timeouts in a row after which the gateway counts as silent for this poll."""


def _whole_setpoint(value: float) -> int:
    if not math.isfinite(value) or value != int(value):
        raise UnsupportedValueError(f"setpoint {value} must be a whole 16..30 °C")
    if not SETPOINT_MIN <= value <= SETPOINT_MAX:
        raise UnsupportedValueError(f"setpoint {value} must be a whole 16..30 °C")
    return int(value)


class IndoorUnitView:
    """
    One indoor unit behind a multi-unit gateway.

    Satisfies :class:`intesis_gw_modbus.ac.AirConditioner`. Setpoints are
    whole degrees Celsius between 16 and 30.
    """

    setpoint_min: Final = float(SETPOINT_MIN)
    setpoint_max: Final = float(SETPOINT_MAX)
    setpoint_step: Final = 1.0

    def __init__(self, component: IndoorUnit, brand: BrandTable) -> None:
        """Wrap a unit's block with the brand's code maps."""
        self.component = component
        self.brand = brand
        self.reachable = True
        """Whether the last poll read this unit's block."""

    @property
    def number(self) -> int:
        """The indoor unit address number."""
        return self.component.number

    @property
    def present(self) -> bool:
        """Whether the gateway currently talks to this unit."""
        return self.reachable and self.component.comm_error is False

    def _live[T](self, value: T) -> T | None:
        """Return a block field, or None while the gateway cannot reach the unit."""
        return value if self.present else None

    @property
    def power(self) -> bool | None:
        """Whether the unit is on."""
        return self._live(self.component.power)

    @property
    def mode(self) -> Mode | None:
        """The operating mode."""
        return _lookup(self.brand.multi_modes, self._live(self.component.mode))

    @property
    def fan_speed(self) -> FanSpeed | None:
        """The fan speed."""
        return _lookup(
            self.brand.multi_fan_speeds, self._live(self.component.fan_speed)
        )

    @property
    def vane(self) -> VanePosition | None:
        """The louver position."""
        return _lookup(
            self.brand.multi_louver_positions, self._live(self.component.louver)
        )

    @property
    def setpoint(self) -> float | None:
        """The target temperature."""
        raw = self._live(self.component.setpoint)
        return None if raw is None else float(raw)

    @property
    def current_temperature(self) -> float | None:
        """The room temperature the unit reports."""
        raw = self._live(self.component.room_temperature)
        return None if raw is None else float(raw)

    @property
    def available_modes(self) -> tuple[Mode, ...]:
        """The modes the brand table maps."""
        return tuple(self.brand.multi_modes.values())

    @property
    def available_fan_speeds(self) -> tuple[FanSpeed, ...]:
        """The fan speeds the brand table maps (no auto on this family)."""
        return tuple(self.brand.multi_fan_speeds.values())

    @property
    def available_vane_positions(self) -> tuple[VanePosition, ...]:
        """The louver positions the brand table maps."""
        return tuple(self.brand.multi_louver_positions.values())

    @property
    def error(self) -> ErrorInfo | None:
        """The decoded error code."""
        return decode_error(self._live(self.component.error_code), self.brand.errors)

    @property
    def remote_control_locked(self) -> bool | None:
        """Whether the wall remote controller is locked out."""
        unlocked = self._live(self.component.remote_control_unlocked)
        return None if unlocked is None else not unlocked

    @property
    def filter_sign(self) -> bool | None:
        """Whether the filter sign is lit."""
        return self._live(self.component.filter_sign)

    @property
    def compressor_on(self) -> bool | None:
        """Whether the compressor runs."""
        return self._live(self.component.compressor_on)

    @property
    def thermo_on(self) -> bool | None:
        """Whether the thermostat calls for output (inverter units only)."""
        return self._live(self.component.thermo_on)

    async def async_set_power(self, on: bool) -> None:  # noqa: FBT001
        """Turn the unit on or off."""
        await self.component.write("power", on)

    async def async_set_mode(self, mode: Mode) -> None:
        """Set the operating mode."""
        await self.component.write(
            "mode", self.brand.code_for(self.brand.multi_modes, mode)
        )

    async def async_set_fan_speed(self, speed: FanSpeed) -> None:
        """Set the fan speed."""
        await self.component.write(
            "fan_speed", self.brand.code_for(self.brand.multi_fan_speeds, speed)
        )

    async def async_set_vane(self, position: VanePosition) -> None:
        """Set the louver position."""
        await self.component.write(
            "louver", self.brand.code_for(self.brand.multi_louver_positions, position)
        )

    async def async_set_setpoint(self, value: float) -> None:
        """Set the target temperature, a whole 16..30 °C."""
        await self.component.write("setpoint", _whole_setpoint(value))

    async def async_set_remote_control_locked(self, locked: bool) -> None:  # noqa: FBT001
        """Lock or unlock the wall remote controller."""
        await self.component.write("remote_control_unlocked", not locked)

    async def async_reset_filter(self) -> None:
        """Clear the filter sign (write-only block offset 11)."""
        await self._command(FILTER_RESET_OFFSET)

    async def async_reset_error(self) -> None:
        """Clear the remote controller error (write-only block offset 12)."""
        await self._command(ERROR_RESET_OFFSET)

    async def _command(self, offset: int) -> None:
        address = self.number * UNIT_STRIDE + offset
        await self.component.modbus_unit.write_register(address, 1)


class IntesisMultiUnitGateway(Device):
    """An INMBSxxx048O000 / 128O000 gateway and the indoor units behind it."""

    def __init__(self, unit: ModbusUnit, *, brand: BrandTable, unit_count: int) -> None:
        """Bind to a unit; which indoor units exist is settled by the first poll."""
        super().__init__(unit)
        self.brand = brand
        self.unit_count = unit_count
        unit.require_timeout(_REQUIRED_TIMEOUT)
        self.status = GatewayStatus(unit)
        self.units: ComponentGroup | None = None  # built by setup
        self.indoor_units: dict[int, IndoorUnitView] = {}
        self._empty: deque[IndoorUnit] = deque()
        self._update_lock = asyncio.Lock()

    async def _async_setup(self) -> None:
        """
        Probe every block once; a unit answering with no comm error is present.

        A block the gateway does not serve means no unit there. Any other
        error propagates, so a busy reply does not drop a unit for good; the
        base class runs setup again on the next poll. A gateway that reports
        no unit at all is treated the same way: it is probably still booting.
        Every block without a unit, refused or not, is re-probed by later polls.
        """
        present: list[IndoorUnit] = []
        empty: list[IndoorUnit] = []
        for number in range(self.unit_count):
            component = IndoorUnit(self.modbus_unit, number)
            try:
                await component.async_update()
            except (IllegalDataAddressError, IllegalFunctionError):
                empty.append(component)
                continue
            if component.comm_error is False:
                present.append(component)
            else:
                empty.append(component)
        if not present:
            raise NoIndoorUnitsError(
                f"none of the {self.unit_count} indoor unit blocks reports a unit"
            )
        self._empty = deque(empty)
        self._adopt(present)

    def _adopt(self, components: Iterable[IndoorUnit]) -> None:
        """Add indoor units, in place so saved references see them, and re-pool."""
        for component in components:
            self.indoor_units[component.number] = IndoorUnitView(component, self.brand)
        ordered = sorted(self.indoor_units.items())
        self.indoor_units.clear()
        self.indoor_units.update(ordered)
        self.units = ComponentGroup(
            self.modbus_unit, [view.component for view in self.indoor_units.values()]
        )

    async def async_update(self) -> UpdateReport:
        """
        Refresh the gateway status and every present indoor unit.

        Each unit's block is read on its own, so one failing block only marks
        that unit unreachable; ``units`` counts as updated when any answered.
        A status timeout alone does not stop the unit reads, but two timeouts
        in a row mean the gateway went silent: the poll stops there, the
        units not read yet are marked unreachable, and the timeout is raised
        when nothing answered at all. Then re-probe the next few empty
        blocks; a unit that has come online since setup joins
        ``indoor_units`` and is polled from now on. A dead link marks every
        known unit unreachable before the error propagates. Overlapping
        calls run one after the other.
        """
        async with self._update_lock:
            return await self._async_update()

    async def _async_update(self) -> UpdateReport:
        await self.async_ensure_setup()
        report = UpdateReport()
        known = list(self.indoor_units.values())
        status_timeout: ModbusTimeoutError | None = None
        try:
            try:
                await self.async_poll(("status",), report)
            except ModbusTimeoutError as err:
                report.failed["status"] = status_timeout = err
            answered, failures, silent = await self._async_update_units(
                known, timeouts=0 if status_timeout is None else 1
            )
            found = [] if silent else await self._async_rediscover()
        except ModbusConnectionError:
            self._mark_unreachable(known)
            raise
        for view in known:
            view.component.notify()
        if silent and status_timeout is not None and not answered:
            raise status_timeout
        if answered or found:
            report.updated.add("units")
        else:
            report.failed["units"] = failures[0]
        return report

    async def _async_update_units(
        self, views: list[IndoorUnitView], *, timeouts: int
    ) -> tuple[int, list[ModbusError], bool]:
        """Read each unit; return how many answered, the failures, and silence."""
        answered = 0
        failures: list[ModbusError] = []
        for index, view in enumerate(views):
            try:
                await view.component.async_update(notify=False)
            except ModbusConnectionError:
                raise
            except ModbusTimeoutError as err:
                view.reachable = False
                failures.append(err)
                timeouts += 1
                if timeouts >= _SILENCE_BUDGET:
                    for unread in views[index + 1 :]:
                        unread.reachable = False
                    return answered, failures, True
            except ModbusError as err:
                view.reachable = False
                failures.append(err)
                timeouts = 0
            else:
                view.reachable = True
                answered += 1
                timeouts = 0
        return answered, failures, False

    def _mark_unreachable(self, views: list[IndoorUnitView]) -> None:
        for view in views:
            view.reachable = False
            view.component.notify()

    async def _async_rediscover(self) -> list[IndoorUnit]:
        """Probe the next empty blocks; a block leaves the queue once it was read."""
        found: list[IndoorUnit] = []
        try:
            for _ in range(min(REDISCOVERY_BATCH, len(self._empty))):
                component = self._empty[0]
                try:
                    await component.async_update()
                except ModbusConnectionError:
                    raise
                except ModbusTimeoutError:
                    self._empty.rotate(-1)
                    break  # do not spend a timeout per block on a slow bus
                except ModbusError:
                    self._empty.rotate(-1)
                    continue
                self._empty.popleft()
                if component.comm_error is False:
                    found.append(component)
                else:
                    self._empty.append(component)
        finally:
            if found:
                self._adopt(found)
        return found

    async def async_read_raw(self, names: Iterable[str] = POLLED) -> Raw:
        """Every register this device reads, undecoded, for diagnostics."""
        return await super().async_read_raw(names)

    @property
    def hw_comm_ok(self) -> bool | None:
        """Whether the gateway reports no hardware communication error."""
        error = self.status.hw_comm_error
        return None if error is None else not error

    async def async_set_all_power(self, on: bool) -> None:  # noqa: FBT001
        """Turn every indoor unit on or off."""
        await self.modbus_unit.write_register(ALL_POWER, int(on))

    async def async_set_all_mode(self, mode: Mode) -> None:
        """Set every indoor unit's operating mode."""
        code = self.brand.code_for(self.brand.multi_modes, mode)
        await self.modbus_unit.write_register(ALL_MODE, code)

    async def async_set_all_setpoint(self, value: float) -> None:
        """Set every indoor unit's setpoint, a whole 16..30 °C."""
        await self.modbus_unit.write_register(ALL_SETPOINT, _whole_setpoint(value))

    async def async_set_all_fan_speed(self, speed: FanSpeed) -> None:
        """Set every indoor unit's fan speed."""
        code = self.brand.code_for(self.brand.multi_fan_speeds, speed)
        await self.modbus_unit.write_register(ALL_FAN, code)

    async def async_set_all_remote_control_locked(self, locked: bool) -> None:  # noqa: FBT001
        """Lock or unlock every indoor unit's wall remote controller."""
        await self.modbus_unit.write_register(ALL_LOCK, int(not locked))


def _lookup[T](mapping: Mapping[int, T], code: int | None) -> T | None:
    return None if code is None else mapping.get(code)
