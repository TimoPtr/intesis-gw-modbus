# Copyright (c) 2026 Timothy (TimoPtr)
"""Intesis INMBS Modbus gateways for air conditioners, on modbus-connection."""

from .ac import AirConditioner
from .brands import BRANDS, BrandTable, brand_for_device_id
from .enums import (
    ControlLock,
    ErrorState,
    FanSpeed,
    GatewayFamily,
    Mode,
    TemperatureFormat,
    VanePosition,
)
from .errors import (
    ErrorInfo,
    IntesisError,
    NoIndoorUnitsError,
    UnsupportedValueError,
    WrongGatewayError,
)
from .models import KNOWN_DEVICE_IDS, MODELS, GatewayModel, model_for_device_id
from .multi_unit.device import IndoorUnitView, IntesisMultiUnitGateway
from .probe import GatewayProbe, async_probe_gateway
from .single_unit.device import IntesisSingleUnitGateway
from .temperature import INIT_VALUE, detect_temperature_format

__all__ = [
    "BRANDS",
    "INIT_VALUE",
    "KNOWN_DEVICE_IDS",
    "MODELS",
    "AirConditioner",
    "BrandTable",
    "ControlLock",
    "ErrorInfo",
    "ErrorState",
    "FanSpeed",
    "GatewayFamily",
    "GatewayModel",
    "GatewayProbe",
    "IndoorUnitView",
    "IntesisError",
    "IntesisMultiUnitGateway",
    "IntesisSingleUnitGateway",
    "Mode",
    "NoIndoorUnitsError",
    "TemperatureFormat",
    "UnsupportedValueError",
    "VanePosition",
    "WrongGatewayError",
    "async_probe_gateway",
    "brand_for_device_id",
    "detect_temperature_format",
    "model_for_device_id",
]
