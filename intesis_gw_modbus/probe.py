# Copyright (c) 2026 Timothy (TimoPtr)
"""Ask a gateway nobody has identified yet what it is."""

from dataclasses import dataclass
from typing import Final

from modbus_connection import IllegalDataAddressError, IllegalFunctionError, ModbusUnit

from .enums import TemperatureFormat
from .models import KNOWN_DEVICE_IDS, GatewayModel, model_for_device_id
from .temperature import detect_temperature_format

# Same addresses as single_unit.components; read one by one because a gateway
# of another family may have none of them.
_VANE_REGISTER: Final = 3
_SETPOINT_REGISTER: Final = 4
_DEVICE_ID_REGISTER: Final = 49


@dataclass(frozen=True, kw_only=True)
class GatewayProbe:
    """What a gateway answered when asked who it is."""

    device_id: int | None
    """Register 49, or ``None`` when the gateway has no such register."""

    model: GatewayModel | None
    """The single-unit model the device id belongs to, if this library has it."""

    unsupported_brand: str | None
    """The brand of a documented single-unit gateway that has no table yet."""

    temperature_format: TemperatureFormat | None
    """The DIP-switch format, or ``None`` while it cannot be told."""

    raw_vane: int | None
    """Register 3 as read; see :meth:`reports_vane`."""

    def reports_vane(self, model: GatewayModel | None = None) -> bool:
        """
        Return whether the gateway reported a vane position of the model's brand.

        The gateway has no capability register for the vane, so this is a hint
        and not a fact: a unit without a vane was never seen reporting one.
        ``model`` names the brand to read the code against when the probe could
        not tell the model itself.
        """
        model = model or self.model
        return model is not None and self.raw_vane in model.brand.vane_positions


async def _async_read_or_none(unit: ModbusUnit, address: int) -> int | None:
    """Read one holding register, or ``None`` if the gateway does not have it."""
    try:
        [value] = await unit.read_holding_registers(address, 1)
    except (IllegalDataAddressError, IllegalFunctionError):
        return None
    return value


async def async_probe_gateway(unit: ModbusUnit) -> GatewayProbe:
    """
    Identify the gateway behind ``unit`` before a device is built for it.

    A register the gateway does not have reads as ``None``, which is how a
    multi-unit gateway answers. Any other failure, a busy or silent gateway
    included, propagates as a ``ModbusError`` so the caller can retry.
    """
    device_id = await _async_read_or_none(unit, _DEVICE_ID_REGISTER)
    raw_setpoint = await _async_read_or_none(unit, _SETPOINT_REGISTER)
    raw_vane = await _async_read_or_none(unit, _VANE_REGISTER)
    return GatewayProbe(
        device_id=device_id,
        model=None if device_id is None else model_for_device_id(device_id),
        unsupported_brand=None
        if device_id is None
        else KNOWN_DEVICE_IDS.get(device_id),
        temperature_format=detect_temperature_format(raw_setpoint),
        raw_vane=raw_vane,
    )
