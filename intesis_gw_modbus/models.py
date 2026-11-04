# Copyright (c) 2026 Timothy (TimoPtr)
"""The Intesis gateway models this library knows."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from .brands import BRANDS, BrandTable
from .brands.mhi import MHI
from .enums import GatewayFamily


@dataclass(frozen=True, kw_only=True)
class GatewayModel:
    """One Intesis gateway part number."""

    name: str
    brand: BrandTable
    family: GatewayFamily
    unit_count: int | None
    """Indoor units a multi-unit gateway addresses; ``None`` for single-unit."""


MODELS: Final[Mapping[str, GatewayModel]] = {
    model.name: model
    for model in (
        GatewayModel(
            name="INMBSMHI001R000",
            brand=MHI,
            family=GatewayFamily.SINGLE_UNIT,
            unit_count=None,
        ),
        GatewayModel(
            name="INMBSMHI048O000",
            brand=MHI,
            family=GatewayFamily.MULTI_UNIT,
            unit_count=48,
        ),
        GatewayModel(
            name="INMBSMHI128O000",
            brand=MHI,
            family=GatewayFamily.MULTI_UNIT,
            unit_count=128,
        ),
    )
}
"""Every gateway model this library models, by part number."""

KNOWN_DEVICE_IDS: Final[Mapping[int, str]] = {
    0x0801: "Daikin",
    0x1500: "Panasonic",
    0x1F00: "Toshiba",
    0x1000: "LG",
    0x1400: "Hitachi",
    0x1200: "Samsung",
}
"""Register 49 values of single-unit gateways documented but not yet tabled."""


def model_for_device_id(device_id: int) -> GatewayModel | None:
    """Return the single-unit model whose brand reports ``device_id``."""
    for model in MODELS.values():
        if (
            model.family is GatewayFamily.SINGLE_UNIT
            and model.brand.device_id == device_id
            and model.brand.key in BRANDS
        ):
            return model
    return None
