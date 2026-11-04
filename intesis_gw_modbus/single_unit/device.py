# Copyright (c) 2026 Timothy (TimoPtr)
"""The single-unit gateway as a typed device."""

from collections.abc import Iterable, Mapping
from typing import Final

from modbus_connection import ModbusUnit
from modbus_connection.model import Device, Raw, UpdateReport

from intesis_gw_modbus.brands.base import BrandTable
from intesis_gw_modbus.enums import (
    ControlLock,
    FanSpeed,
    Mode,
    TemperatureFormat,
    VanePosition,
)
from intesis_gw_modbus.errors import (
    ErrorInfo,
    UnsupportedValueError,
    WrongGatewayError,
    decode_error,
)
from intesis_gw_modbus.temperature import (
    INIT_VALUE,
    detect_temperature_format,
    from_celsius,
    setpoint_step,
    to_celsius,
)

from .components import (
    Control,
    Diagnostics,
    Identity,
    Limits,
    Lock,
    Temperatures,
    Window,
)

READINGS: Final = ("control", "limits", "window", "lock", "temperatures")
"""Sub-systems that change on their own and are polled every cycle."""

SETTINGS: Final = ("diagnostics",)
"""Sub-systems that only change when someone configures the gateway."""

ALL: Final = ("identity", *READINGS, *SETTINGS)

CONTROL_LOCK_CODES: Final[Mapping[int, ControlLock]] = {
    0: ControlLock.REMOTE_UNLOCK,
    1: ControlLock.LOCK_ON_OFF,
    2: ControlLock.LOCK_ALL,
    3: ControlLock.REMOTE_ONLY,
}

DEFAULT_SETPOINT_MIN: Final = 16.0
DEFAULT_SETPOINT_MAX: Final = 30.0
DEFAULT_FAN_SPEED_COUNT: Final = 3

ERROR_RESET_REGISTER: Final = 45
GATEWAY_RESET_REGISTER: Final = 99
EXTERNAL_TEMPERATURE_REGISTER: Final = 22

_REQUIRED_TIMEOUT: Final = 3.0
_MESSAGE_SPACING: Final = 0.02


class IntesisSingleUnitGateway(Device):
    """
    An INMBSxxx001R000 gateway and the one AC unit behind it.

    Satisfies :class:`intesis_gw_modbus.ac.AirConditioner`. Temperatures are
    degrees Celsius whatever the gateway's DIP-switch format.
    """

    def __init__(
        self,
        unit: ModbusUnit,
        *,
        brand: BrandTable,
        temperature_format: TemperatureFormat,
    ) -> None:
        """Bind to a unit and ask for the timing a 9600-baud RTU link needs."""
        super().__init__(unit)
        self.brand = brand
        self.temperature_format = temperature_format
        unit.require_timeout(_REQUIRED_TIMEOUT)
        unit.set_message_spacing(_MESSAGE_SPACING)
        self.control = Control(unit)
        self.limits = Limits(unit)
        self.window = Window(unit)
        self.lock = Lock(unit)
        self.identity = Identity(unit)
        self.diagnostics = Diagnostics(unit)
        self.temperatures = Temperatures(unit)

    async def _async_setup(self) -> None:
        """Read the identity block once and check it is the expected brand."""
        await self.identity.async_update()
        expected = self.brand.device_id
        if expected is not None and self.identity.device_id != expected:
            raise WrongGatewayError(
                f"device id {self.identity.device_id:#06x} is not "
                f"{self.brand.name} ({expected:#06x})"
            )

    async def async_update_readings(self) -> UpdateReport:
        """Refresh what the unit reports and does."""
        return await self.async_poll(READINGS)

    async def async_update_settings(self) -> UpdateReport:
        """Refresh the gateway's own behaviour switches and counters."""
        return await self.async_poll(SETTINGS)

    async def async_update(self) -> UpdateReport:
        """Refresh every polled sub-system."""
        report = await self.async_poll(READINGS)
        return await self.async_poll(SETTINGS, report)

    async def async_read_raw(self, names: Iterable[str] = ALL) -> Raw:
        """Every register this device reads, undecoded, for diagnostics."""
        return await super().async_read_raw(names)

    # -- conversions -------------------------------------------------------

    def _celsius(self, raw: int | None) -> float | None:
        return to_celsius(raw, self.temperature_format)

    def _raw(self, celsius: float) -> int:
        return from_celsius(celsius, self.temperature_format)

    # -- AirConditioner ----------------------------------------------------

    @property
    def power(self) -> bool | None:
        """Whether the unit is on."""
        return self.control.power

    @property
    def mode(self) -> Mode | None:
        """The operating mode."""
        return _lookup(self.brand.modes, self.control.mode)

    @property
    def fan_speed(self) -> FanSpeed | None:
        """The fan speed."""
        return _lookup(self.brand.fan_speeds, self.control.fan_speed)

    @property
    def vane(self) -> VanePosition | None:
        """The vane position."""
        return _lookup(self.brand.vane_positions, self.control.vane)

    @property
    def setpoint(self) -> float | None:
        """The target temperature."""
        return self._celsius(self.control.setpoint)

    @property
    def current_temperature(self) -> float | None:
        """The ambient temperature the unit regulates on (register 5)."""
        return self._celsius(self.control.ambient_temperature)

    @property
    def setpoint_min(self) -> float:
        """The lowest setpoint the unit accepts right now."""
        value = self._celsius(self.limits.setpoint_min)
        return DEFAULT_SETPOINT_MIN if value is None else value

    @property
    def setpoint_max(self) -> float:
        """The highest setpoint the unit accepts right now."""
        value = self._celsius(self.limits.setpoint_max)
        return DEFAULT_SETPOINT_MAX if value is None else value

    @property
    def setpoint_step(self) -> float:
        """The finest setpoint step the format can express."""
        return setpoint_step(self.temperature_format)

    @property
    def available_modes(self) -> tuple[Mode, ...]:
        """The modes the brand table maps."""
        return tuple(self.brand.modes.values())

    @property
    def available_fan_speeds(self) -> tuple[FanSpeed, ...]:
        """Auto plus the speeds the unit reports having (register 21)."""
        count = self.max_fan_speeds
        if count is None:
            count = DEFAULT_FAN_SPEED_COUNT
        return (
            FanSpeed.AUTO,
            *(s for code, s in self.brand.fan_speeds.items() if 1 <= code <= count),
        )

    @property
    def available_vane_positions(self) -> tuple[VanePosition, ...]:
        """The vane positions the brand table maps."""
        return tuple(self.brand.vane_positions.values())

    @property
    def error(self) -> ErrorInfo | None:
        """The decoded error code register."""
        return decode_error(self.control.error_code, self.brand.errors)

    async def async_set_power(self, on: bool) -> None:  # noqa: FBT001
        """Turn the unit on or off."""
        await self.control.write("power", on)

    async def async_set_mode(self, mode: Mode) -> None:
        """Set the operating mode."""
        await self.control.write("mode", self.brand.code_for(self.brand.modes, mode))

    async def async_set_fan_speed(self, speed: FanSpeed) -> None:
        """Set the fan speed; only speeds the unit reports having are accepted."""
        if speed not in self.available_fan_speeds:
            raise UnsupportedValueError(
                f"fan speed {speed} is not available on this unit"
            )
        await self.control.write(
            "fan_speed", self.brand.code_for(self.brand.fan_speeds, speed)
        )

    async def async_set_vane(self, position: VanePosition) -> None:
        """Set the vane position."""
        await self.control.write(
            "vane", self.brand.code_for(self.brand.vane_positions, position)
        )

    async def async_set_setpoint(self, value: float) -> None:
        """Set the target temperature, within the unit's current limits."""
        if not self.setpoint_min <= value <= self.setpoint_max:
            raise UnsupportedValueError(
                f"setpoint {value} is outside {self.setpoint_min}..{self.setpoint_max}"
            )
        await self.control.write("setpoint", self._raw(value))

    # -- the rest of the single-unit surface -------------------------------

    @property
    def real_setpoint(self) -> float | None:
        """The setpoint the unit applies (register 23)."""
        return self._celsius(self.limits.real_setpoint)

    @property
    def external_temperature(self) -> float | None:
        """The external reference temperature last written (register 22)."""
        return self._celsius(self.limits.external_temperature)

    @property
    def outdoor_intake_temperature(self) -> float | None:
        """Outdoor intake temperature (register 60)."""
        return self._celsius(self.temperatures.outdoor_intake)

    @property
    def input_reference_temperature(self) -> float | None:
        """Input reference temperature (register 65)."""
        return self._celsius(self.temperatures.input_reference)

    @property
    def return_path_temperature(self) -> float | None:
        """Return path temperature (register 66)."""
        return self._celsius(self.temperatures.return_path)

    @property
    def detected_temperature_format(self) -> TemperatureFormat | None:
        """The format the raw setpoint implies, to catch a DIP-switch change."""
        return detect_temperature_format(self.control.setpoint)

    @property
    def alarm(self) -> bool | None:
        """Whether the unit reports an alarm condition."""
        return self.control.alarm

    @property
    def window_open(self) -> bool | None:
        """Whether the gateway considers a window open (register 31)."""
        return self.window.window_open

    @property
    def window_contact(self) -> bool | None:
        """The window contact state written to the gateway (register 6)."""
        return self.control.window_contact

    @property
    def window_timeout_minutes(self) -> int | None:
        """Minutes before an open window switches the unit off."""
        return self.control.window_timeout

    @property
    def gateway_disabled(self) -> bool | None:
        """Whether the gateway is disabled (register 7)."""
        return self.control.gateway_disabled

    @property
    def remote_control_disabled(self) -> bool | None:
        """Whether the wall remote controller is disabled (register 8)."""
        return self.control.remote_control_disabled

    @property
    def block_periodic_sendings(self) -> bool | None:
        """Whether unchanged commands are withheld from the unit (register 97)."""
        return self.diagnostics.block_periodic_sendings

    @property
    def is_master(self) -> bool | None:
        """Whether the gateway is the master on the XY bus (register 98)."""
        return self.diagnostics.is_master

    @property
    def control_lock(self) -> ControlLock | None:
        """The Center/Remote lock state (register 46)."""
        return _lookup(CONTROL_LOCK_CODES, self.lock.control_lock)

    @property
    def operation_hours(self) -> int | None:
        """Hours the unit has been on."""
        return self.control.operation_hours

    @property
    def undervoltage_hours(self) -> int | None:
        """Hours of under-voltage counted by the gateway."""
        return self.diagnostics.undervoltage_hours

    @property
    def error_address(self) -> int | None:
        """The indoor unit number reporting the error (register 81)."""
        return self.diagnostics.error_address

    @property
    def max_fan_speeds(self) -> int | None:
        """How many fan speeds the unit has (register 21)."""
        return self.limits.max_fan_speeds

    @property
    def device_id(self) -> int | None:
        """The gateway's device id (register 49)."""
        return self.identity.device_id

    @property
    def software_version(self) -> str | None:
        """The gateway's software version register, as a decimal string."""
        raw = self.identity.software_version
        return None if raw is None else str(raw)

    async def async_set_external_temperature(self, value: float | None) -> None:
        """Feed the unit an external reference temperature; ``None`` withdraws it."""
        if value is None:
            await self.modbus_unit.write_register(
                EXTERNAL_TEMPERATURE_REGISTER, INIT_VALUE
            )
            return
        await self.limits.write("external_temperature", self._raw(value))

    async def async_set_window_contact(self, open: bool) -> None:  # noqa: A002, FBT001
        """Tell the gateway whether a window is open."""
        await self.control.write("window_contact", open)

    async def async_set_window_timeout(self, minutes: int) -> None:
        """Set how long a window may stay open before the unit switches off."""
        await self.control.write("window_timeout", minutes)

    async def async_set_gateway_disabled(self, disabled: bool) -> None:  # noqa: FBT001
        """Disable or enable the gateway."""
        await self.control.write("gateway_disabled", disabled)

    async def async_set_remote_control_disabled(self, disabled: bool) -> None:  # noqa: FBT001
        """Disable or enable the wall remote controller."""
        await self.control.write("remote_control_disabled", disabled)

    async def async_set_block_periodic_sendings(self, blocked: bool) -> None:  # noqa: FBT001
        """Withhold unchanged commands from the unit, or send them all."""
        await self.diagnostics.write("block_periodic_sendings", blocked)

    async def async_set_master(self, master: bool) -> None:  # noqa: FBT001
        """Make the gateway master or slave on the XY bus."""
        await self.diagnostics.write("is_master", master)

    async def async_reset_error(self) -> None:
        """Acknowledge the unit's error (write-only register 45)."""
        await self.modbus_unit.write_register(ERROR_RESET_REGISTER, 1)

    async def async_reset_gateway(self) -> None:
        """Reset the gateway (write-only register 99)."""
        await self.modbus_unit.write_register(GATEWAY_RESET_REGISTER, 1)


def _lookup[T](mapping: Mapping[int, T], code: int | None) -> T | None:
    return None if code is None else mapping.get(code)
