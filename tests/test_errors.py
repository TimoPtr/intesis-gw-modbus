# Copyright (c) 2026 Timothy (TimoPtr)
"""Error code decoding."""

from intesis_gw_modbus.enums import ErrorState
from intesis_gw_modbus.errors import (
    COMM_ERROR_CODE,
    INIT_ERROR_CODE,
    ErrorInfo,
    decode_error,
)

TABLE = {1: ("E1", "Remote controller communication error")}


def test_no_error() -> None:
    assert decode_error(0, TABLE) == ErrorInfo(0, ErrorState.NONE, None, None)


def test_unread() -> None:
    assert decode_error(None, TABLE) is None


def test_initialising() -> None:
    info = decode_error(INIT_ERROR_CODE, TABLE)
    assert info is not None
    assert info.state is ErrorState.INITIALISING


def test_comm_error() -> None:
    info = decode_error(COMM_ERROR_CODE, TABLE)
    assert info is not None
    assert info.state is ErrorState.COMMUNICATION_ERROR


def test_known_unit_error() -> None:
    assert decode_error(1, TABLE) == ErrorInfo(
        1, ErrorState.UNIT_ERROR, "E1", "Remote controller communication error"
    )


def test_unknown_unit_error() -> None:
    assert decode_error(99, TABLE) == ErrorInfo(99, ErrorState.UNIT_ERROR, None, None)
