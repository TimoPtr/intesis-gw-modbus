# Copyright (c) 2026 Timothy (TimoPtr)
"""The package's public surface."""

import intesis_gw_modbus as lib


def test_all_exports_resolve() -> None:
    for name in lib.__all__:
        assert getattr(lib, name) is not None


def test_key_names_present() -> None:
    assert {
        "IntesisSingleUnitGateway",
        "IntesisMultiUnitGateway",
        "MODELS",
        "detect_temperature_format",
        "async_probe_gateway",
        "GatewayProbe",
    } <= set(lib.__all__)
