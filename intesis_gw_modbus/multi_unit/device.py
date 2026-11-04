# Copyright (c) 2026 Timothy (TimoPtr)
"""The multi-unit gateway as a typed device, one view per indoor unit."""

from collections.abc import Iterable, Mapping
from typing import Final

from modbus_connection import ModbusExceptionError, ModbusUnit
from modbus_connection.model import ComponentGroup, Device, Raw, UpdateReport

from intesis_gw_modbus.brands.base import BrandTable
from intesis_gw_modbus.enums import FanSpeed, Mode, VanePosition
from intesis_gw_modbus.errors import ErrorInfo, UnsupportedValueError, decode_error

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

_REQUIRED_TIMEOUT: Final = 3.0


def _whole_setpoint(value: float) -> int:
    if value != int(value) or not SETPOINT_MIN <= value <= SETPOINT_MAX:
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

    @property
    def number(self) -> int:
        """The indoor unit address number."""
        return self.component.number

    @property
    def present(self) -> bool:
        """Whether the gateway currently talks to this unit."""
        return self.component.comm_error is False

    @property
    def power(self) -> bool | None:
        """Whether the unit is on."""
        return self.component.power

    @property
    def mode(self) -> Mode | None:
        """The operating mode."""
        return _lookup(self.brand.multi_modes, self.component.mode)

    @property
    def fan_speed(self) -> FanSpeed | None:
        """The fan speed."""
        return _lookup(self.brand.multi_fan_speeds, self.component.fan_speed)

    @property
    def vane(self) -> VanePosition | None:
        """The louver position."""
        return _lookup(self.brand.multi_louver_positions, self.component.louver)

    @property
    def setpoint(self) -> float | None:
        """The target temperature."""
        raw = self.component.setpoint
        return None if raw is None else float(raw)

    @property
    def current_temperature(self) -> float | None:
        """The room temperature the unit reports."""
        raw = self.component.room_temperature
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
        return decode_error(self.component.error_code, self.brand.errors)

    @property
    def remote_control_locked(self) -> bool | None:
        """Whether the wall remote controller is locked out."""
        unlocked = self.component.remote_control_unlocked
        return None if unlocked is None else not unlocked

    @property
    def filter_sign(self) -> bool | None:
        """Whether the filter sign is lit."""
        return self.component.filter_sign

    @property
    def compressor_on(self) -> bool | None:
        """Whether the compressor runs."""
        return self.component.compressor_on

    @property
    def thermo_on(self) -> bool | None:
        """Whether the thermostat calls for output (inverter units only)."""
        return self.component.thermo_on

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
        self.units: ComponentGroup | None = None
        self.indoor_units: dict[int, IndoorUnitView] = {}

    async def _async_setup(self) -> None:
        """Probe every block once; a unit answering with no comm error is present."""
        present: list[IndoorUnit] = []
        for number in range(self.unit_count):
            component = IndoorUnit(self.modbus_unit, number)
            try:
                await component.async_update()
            except ModbusExceptionError:
                continue
            if component.comm_error is False:
                present.append(component)
        self.indoor_units = {c.number: IndoorUnitView(c, self.brand) for c in present}
        self.units = ComponentGroup(self.modbus_unit, present) if present else None

    async def async_update(self) -> UpdateReport:
        """Refresh the gateway status and every present indoor unit."""
        return await self.async_poll(POLLED)

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
