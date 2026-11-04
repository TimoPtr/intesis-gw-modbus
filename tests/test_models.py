# Copyright (c) 2026 Timothy (TimoPtr)
"""Gateway model registry."""

from intesis_gw_modbus.enums import GatewayFamily
from intesis_gw_modbus.models import KNOWN_DEVICE_IDS, MODELS, model_for_device_id


def test_models() -> None:
    assert MODELS["INMBSMHI001R000"].family is GatewayFamily.SINGLE_UNIT
    assert MODELS["INMBSMHI048O000"].unit_count == 48
    assert MODELS["INMBSMHI128O000"].unit_count == 128


def test_model_for_device_id() -> None:
    assert model_for_device_id(0x0F00) is MODELS["INMBSMHI001R000"]
    assert model_for_device_id(0x0801) is None


def test_known_ids_do_not_collide() -> None:
    assert 0x0F00 not in KNOWN_DEVICE_IDS
    assert len(KNOWN_DEVICE_IDS) == 6
