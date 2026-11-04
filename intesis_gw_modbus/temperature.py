# Copyright (c) 2026 Timothy (TimoPtr)
"""Temperature register scaling for the three DIP-switch formats."""

from typing import Final

from .enums import TemperatureFormat

INIT_VALUE: Final = 0x8000
"""Raw value every data register holds while the gateway initialises."""

_CELSIUS_RANGE: Final = range(16, 32)
_FAHRENHEIT_RANGE: Final = range(60, 91)
_DECICELSIUS_RANGE: Final = range(160, 311)


def to_celsius(raw: int | None, fmt: TemperatureFormat) -> float | None:
    """Decode a temperature register into degrees Celsius."""
    if raw is None:
        return None
    if fmt is TemperatureFormat.DECICELSIUS:
        return raw / 10
    if fmt is TemperatureFormat.FAHRENHEIT:
        return round((raw - 32) * 5 / 9, 1)
    return float(raw)


def from_celsius(value: float, fmt: TemperatureFormat) -> int:
    """Encode degrees Celsius into the register value the gateway expects."""
    if fmt is TemperatureFormat.DECICELSIUS:
        return round(value * 10)
    if fmt is TemperatureFormat.FAHRENHEIT:
        return round(value * 9 / 5 + 32)
    return round(value)


def detect_temperature_format(raw_setpoint: int | None) -> TemperatureFormat | None:
    """Infer the format from a raw setpoint; the three ranges do not overlap."""
    if raw_setpoint is None:
        return None
    if raw_setpoint in _CELSIUS_RANGE:
        return TemperatureFormat.CELSIUS
    if raw_setpoint in _FAHRENHEIT_RANGE:
        return TemperatureFormat.FAHRENHEIT
    if raw_setpoint in _DECICELSIUS_RANGE:
        return TemperatureFormat.DECICELSIUS
    return None


def setpoint_step(fmt: TemperatureFormat) -> float:
    """
    Return the setpoint step a user interface should offer.

    Whole-degree formats step by 1 in the gateway's own unit; the value is
    not converted for Fahrenheit because Home Assistant applies the step in
    the display unit, where 1 °F is exact. Decicelsius units accept halves.
    """
    return 0.5 if fmt is TemperatureFormat.DECICELSIUS else 1.0
