# Copyright (c) 2026 Timothy (TimoPtr)
"""Brand tables: one module per AC brand, registered here."""

from collections.abc import Mapping
from typing import Final

from .base import BrandTable
from .mhi import MHI

BRANDS: Final[Mapping[str, BrandTable]] = {MHI.key: MHI}
"""Every brand this library has a table for, by key."""


def brand_for_device_id(device_id: int) -> BrandTable | None:
    """Return the brand whose single-unit gateway reports ``device_id``."""
    for brand in BRANDS.values():
        if brand.device_id == device_id:
            return brand
    return None


__all__ = ["BRANDS", "BrandTable", "brand_for_device_id"]
