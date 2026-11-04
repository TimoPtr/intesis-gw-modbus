# Copyright (c) 2026 Timothy (TimoPtr)
"""Enumerations shared by every Intesis gateway family."""

from enum import StrEnum


class TemperatureFormat(StrEnum):
    """How the gateway's DIP switches scale temperature registers."""

    CELSIUS = "celsius"
    DECICELSIUS = "decicelsius"
    FAHRENHEIT = "fahrenheit"


class GatewayFamily(StrEnum):
    """The two Intesis INMBS gateway families."""

    SINGLE_UNIT = "single_unit"
    MULTI_UNIT = "multi_unit"


class Mode(StrEnum):
    """Air conditioner operating mode."""

    AUTO = "auto"
    HEAT = "heat"
    DRY = "dry"
    FAN = "fan"
    COOL = "cool"


class FanSpeed(StrEnum):
    """Air conditioner fan speed."""

    AUTO = "auto"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    POWERFUL = "powerful"


class VanePosition(StrEnum):
    """Air conditioner vane (louver) position."""

    SWING = "swing"
    POSITION_1 = "position_1"
    POSITION_2 = "position_2"
    POSITION_3 = "position_3"
    POSITION_4 = "position_4"


class ControlLock(StrEnum):
    """Single-unit gateway Center/Remote lock state (register 46)."""

    REMOTE_UNLOCK = "remote_unlock"
    LOCK_ON_OFF = "lock_on_off"
    LOCK_ALL = "lock_all"
    REMOTE_ONLY = "remote_only"


class ErrorState(StrEnum):
    """Brand-independent summary of the error code register."""

    NONE = "none"
    INITIALISING = "initialising"
    COMMUNICATION_ERROR = "communication_error"
    UNIT_ERROR = "unit_error"
