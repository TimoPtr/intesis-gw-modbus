# Copyright (c) 2026 Timothy (TimoPtr)
"""Error code decoding and the library's exceptions."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from .enums import ErrorState

INIT_ERROR_CODE: Final = 65532
"""Error code reported while the gateway initialises (about two minutes)."""

COMM_ERROR_CODE: Final = 65535
"""Error code reported when the gateway cannot talk to the AC unit."""

type ErrorTable = Mapping[int, tuple[str, str]]
"""Brand error table: code -> (remote-controller code, description)."""


@dataclass(frozen=True)
class ErrorInfo:
    """A decoded error code register."""

    code: int
    state: ErrorState
    remote_code: str | None
    description: str | None


def decode_error(code: int | None, table: ErrorTable) -> ErrorInfo | None:
    """Decode an error code register against a brand's error table."""
    if code is None:
        return None
    if code == 0:
        return ErrorInfo(code, ErrorState.NONE, None, None)
    if code == INIT_ERROR_CODE:
        return ErrorInfo(code, ErrorState.INITIALISING, None, None)
    if code == COMM_ERROR_CODE:
        return ErrorInfo(code, ErrorState.COMMUNICATION_ERROR, None, None)
    remote_code, description = table.get(code, (None, None))
    return ErrorInfo(code, ErrorState.UNIT_ERROR, remote_code, description)


class IntesisError(Exception):
    """Base class for errors raised by this library."""


class WrongGatewayError(IntesisError):
    """The gateway's device id does not match the brand it was set up as."""


class UnsupportedValueError(IntesisError, ValueError):
    """A value the gateway, unit or brand cannot accept."""
