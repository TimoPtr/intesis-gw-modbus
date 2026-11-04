# Copyright (c) 2026 Timothy (TimoPtr)
"""The data that distinguishes one AC brand's Intesis gateways from another's."""

from collections.abc import Mapping
from dataclasses import dataclass

from intesis_gw_modbus.enums import FanSpeed, Mode, VanePosition
from intesis_gw_modbus.errors import ErrorTable, UnsupportedValueError


@dataclass(frozen=True, kw_only=True)
class BrandTable:
    """
    Register code maps and the error table of one brand.

    The single-unit maps decode registers 1, 2 and 3 of an INMBSxxx001R000
    gateway. The multi-unit maps decode block offsets 2, 4 and 6 of an
    INMBSxxxXXXO000 gateway. Both families share the error table.
    """

    key: str
    name: str
    device_id: int | None
    modes: Mapping[int, Mode]
    fan_speeds: Mapping[int, FanSpeed]
    vane_positions: Mapping[int, VanePosition]
    multi_modes: Mapping[int, Mode]
    multi_fan_speeds: Mapping[int, FanSpeed]
    multi_louver_positions: Mapping[int, VanePosition]
    errors: ErrorTable

    def code_for[T](self, mapping: Mapping[int, T], value: T) -> int:
        """Return the register code a mapping assigns to ``value``."""
        for code, candidate in mapping.items():
            if candidate == value:
                return code
        raise UnsupportedValueError(f"{value!r} is not supported by {self.name}")
