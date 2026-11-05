# Copyright (c) 2026 Timothy (TimoPtr)
"""Temperature format conversion and detection."""

import math

import pytest

from intesis_gw_modbus.enums import TemperatureFormat as F
from intesis_gw_modbus.errors import UnsupportedValueError
from intesis_gw_modbus.temperature import (
    INIT_VALUE,
    detect_temperature_format,
    from_celsius,
    setpoint_step,
    to_celsius,
)


@pytest.mark.parametrize(
    ("raw", "fmt", "expected"),
    [
        (22, F.CELSIUS, 22.0),
        (-3, F.CELSIUS, -3.0),
        (215, F.DECICELSIUS, 21.5),
        (-15, F.DECICELSIUS, -1.5),
        (72, F.FAHRENHEIT, 22.2),
        (32, F.FAHRENHEIT, 0.0),
        (None, F.CELSIUS, None),
        (None, F.DECICELSIUS, None),
        (None, F.FAHRENHEIT, None),
    ],
)
def test_to_celsius(raw: int | None, fmt: F, expected: float | None) -> None:
    assert to_celsius(raw, fmt) == expected


@pytest.mark.parametrize(
    ("value", "fmt", "expected"),
    [
        (21.5, F.CELSIUS, 22),
        (21.4, F.CELSIUS, 21),
        (21.5, F.DECICELSIUS, 215),
        (21.44, F.DECICELSIUS, 214),
        (22.0, F.FAHRENHEIT, 72),
        (22.2, F.FAHRENHEIT, 72),
    ],
)
def test_from_celsius(value: float, fmt: F, expected: int) -> None:
    assert from_celsius(value, fmt) == expected


def test_fahrenheit_round_trip() -> None:
    raw = from_celsius(22.0, F.FAHRENHEIT)
    assert raw == 72
    celsius = to_celsius(raw, F.FAHRENHEIT)
    assert celsius is not None
    assert from_celsius(celsius, F.FAHRENHEIT) == 72  # no drift


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (16, F.CELSIUS),
        (31, F.CELSIUS),
        (60, F.FAHRENHEIT),
        (90, F.FAHRENHEIT),
        (160, F.DECICELSIUS),
        (310, F.DECICELSIUS),
        (INIT_VALUE, None),
        (None, None),
        (0, None),
        (32, None),
        (59, None),
        (91, None),
        (159, None),
        (311, None),
    ],
)
def test_detect_temperature_format(raw: int | None, expected: F | None) -> None:
    assert detect_temperature_format(raw) == expected


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("fmt", list(F))
def test_from_celsius_rejects_non_finite(value: float, fmt: F) -> None:
    with pytest.raises(UnsupportedValueError):
        from_celsius(value, fmt)


@pytest.mark.parametrize(
    ("value", "fmt"),
    [
        (-3276.8, F.DECICELSIUS),  # would encode to the 0x8000 sentinel
        (3300.0, F.DECICELSIUS),
        (40000.0, F.CELSIUS),
        (-40000.0, F.FAHRENHEIT),
    ],
)
def test_from_celsius_rejects_values_outside_the_register(value: float, fmt: F) -> None:
    with pytest.raises(UnsupportedValueError):
        from_celsius(value, fmt)


def test_setpoint_step() -> None:
    assert setpoint_step(F.DECICELSIUS) == 0.5
    assert setpoint_step(F.CELSIUS) == 1.0
    assert setpoint_step(F.FAHRENHEIT) == 1.0
