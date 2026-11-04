# Copyright (c) 2026 Timothy (TimoPtr)
"""The data that distinguishes one AC brand's Intesis gateways from another's."""

from collections.abc import Mapping
from dataclasses import dataclass, field

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
    """Register 2 codes on a unit with the most speeds the brand supports."""
    fan_speed_sets: Mapping[int, Mapping[int, FanSpeed]] = field(default_factory=dict)
    """Register 2 codes by the unit's speed count (register 21), where they
    differ from ``fan_speeds``: a 2-speed MHI unit uses 1 Low / 2 High."""
    vane_positions: Mapping[int, VanePosition]
    multi_modes: Mapping[int, Mode]
    multi_fan_speeds: Mapping[int, FanSpeed]
    multi_louver_positions: Mapping[int, VanePosition]
    errors: ErrorTable

    def fan_speeds_for(self, count: int | None) -> Mapping[int, FanSpeed]:
        """Return the register 2 code map for a unit with ``count`` speeds."""
        if count is None:
            return self.fan_speeds
        return self.fan_speed_sets.get(count, self.fan_speeds)

    def code_for[T](self, mapping: Mapping[int, T], value: T) -> int:
        """Return the register code a mapping assigns to ``value``."""
        for code, candidate in mapping.items():
            if candidate == value:
                return code
        raise UnsupportedValueError(f"{value!r} is not supported by {self.name}")
