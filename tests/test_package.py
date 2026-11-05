# Copyright (c) 2026 Timothy (TimoPtr)
"""The package is installed as a distribution."""

from importlib.metadata import version

import intesis_gw_modbus


def test_distribution_is_installed() -> None:
    assert intesis_gw_modbus is not None
    # setuptools-scm gives a version even without a tag.
    assert version("intesis-gw-modbus")
