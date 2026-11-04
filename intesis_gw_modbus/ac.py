# Copyright (c) 2026 Timothy (TimoPtr)
"""The interface every controllable air conditioner exposes."""

from typing import Protocol

from .enums import FanSpeed, Mode, VanePosition
from .errors import ErrorInfo


class AirConditioner(Protocol):
    """
    One controllable air conditioner, whatever gateway family it sits behind.

    A single-unit gateway is itself an air conditioner. A multi-unit gateway
    exposes one per indoor unit. Temperatures are degrees Celsius.
    """

    @property
    def power(self) -> bool | None:
        """Whether the unit is on."""

    @property
    def mode(self) -> Mode | None:
        """The operating mode."""

    @property
    def fan_speed(self) -> FanSpeed | None:
        """The fan speed."""

    @property
    def vane(self) -> VanePosition | None:
        """The vane position."""

    @property
    def setpoint(self) -> float | None:
        """The target temperature."""

    @property
    def current_temperature(self) -> float | None:
        """The temperature the unit regulates on."""

    @property
    def setpoint_min(self) -> float:
        """The lowest setpoint the unit accepts."""

    @property
    def setpoint_max(self) -> float:
        """The highest setpoint the unit accepts."""

    @property
    def setpoint_step(self) -> float:
        """The finest setpoint step the unit accepts."""

    @property
    def available_modes(self) -> tuple[Mode, ...]:
        """The modes the unit can be put in."""

    @property
    def available_fan_speeds(self) -> tuple[FanSpeed, ...]:
        """The fan speeds the unit offers."""

    @property
    def available_vane_positions(self) -> tuple[VanePosition, ...]:
        """The vane positions the unit offers."""

    @property
    def error(self) -> ErrorInfo | None:
        """The decoded error code register."""

    async def async_set_power(self, on: bool) -> None:  # noqa: FBT001
        """Turn the unit on or off."""

    async def async_set_mode(self, mode: Mode) -> None:
        """Set the operating mode."""

    async def async_set_fan_speed(self, speed: FanSpeed) -> None:
        """Set the fan speed."""

    async def async_set_vane(self, position: VanePosition) -> None:
        """Set the vane position."""

    async def async_set_setpoint(self, value: float) -> None:
        """Set the target temperature in degrees Celsius."""
