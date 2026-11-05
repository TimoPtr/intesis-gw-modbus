# Copyright (c) 2026 Timothy (TimoPtr)
"""Brand tables."""

import pytest

from intesis_gw_modbus.brands import BRANDS, brand_for_device_id
from intesis_gw_modbus.brands.base import BrandTable
from intesis_gw_modbus.brands.mhi import MHI
from intesis_gw_modbus.enums import FanSpeed, Mode, VanePosition
from intesis_gw_modbus.errors import UnsupportedValueError


def test_registry() -> None:
    assert BRANDS["mhi"] is MHI
    assert brand_for_device_id(0x0F00) is MHI
    assert brand_for_device_id(0x1234) is None


def test_mhi_single_unit_codes() -> None:
    assert MHI.modes[4] is Mode.COOL
    assert MHI.fan_speeds[4] is FanSpeed.POWERFUL
    assert MHI.vane_positions[10] is VanePosition.SWING


def test_mhi_multi_unit_codes() -> None:
    assert MHI.multi_modes[0] is Mode.COOL
    assert MHI.multi_fan_speeds[3] is FanSpeed.POWERFUL
    assert MHI.multi_louver_positions[0] is VanePosition.SWING


@pytest.mark.parametrize("brand", BRANDS.values(), ids=lambda b: b.key)
def test_every_code_round_trips(brand: BrandTable) -> None:
    for mapping in (
        brand.modes,
        brand.fan_speeds,
        brand.vane_positions,
        brand.multi_modes,
        brand.multi_fan_speeds,
        brand.multi_louver_positions,
    ):
        for code, value in mapping.items():
            assert brand.code_for(mapping, value) == code


def test_code_for_rejects_unmapped() -> None:
    with pytest.raises(UnsupportedValueError):
        MHI.code_for(MHI.multi_fan_speeds, FanSpeed.AUTO)


def test_mhi_error_table() -> None:
    assert len(MHI.errors) == 43
    assert MHI.errors[1] == ("E1", "Remote controller communication error")
    assert MHI.errors[63] == ("E63", "Emergency stop")
    assert all(remote == f"E{code}" for code, (remote, _) in MHI.errors.items())


def test_fan_speeds_for_count() -> None:
    assert MHI.fan_speeds_for(None) is MHI.fan_speeds
    assert MHI.fan_speeds_for(4) is MHI.fan_speeds
    assert MHI.fan_speeds_for(2) == {
        0: FanSpeed.AUTO,
        1: FanSpeed.LOW,
        2: FanSpeed.HIGH,
    }
