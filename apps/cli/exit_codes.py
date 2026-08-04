"""Stable CLI exit codes for xqueue."""

from __future__ import annotations

from enum import IntEnum

from xqueue.core.errors import (
    ConfigurationError,
    ConflictError,
    NotFoundError,
    OperationTimeoutError,
    RuntimeExecutionError,
    ValidationError,
    XqueueError,
)


class ExitCode(IntEnum):
    SUCCESS = 0
    VALIDATION_ERROR = 2
    NOT_FOUND = 3
    CONFLICT = 4
    RUNTIME_ERROR = 5
    TIMEOUT = 124
    INTERRUPTED = 130


def map_error_to_exit_code(error: XqueueError) -> ExitCode:
    """Map domain/application errors to stable shell exit codes."""
    # Configuration that will not compose is a bad invocation, which is what
    # exit code 2 already means to a shell.
    if isinstance(error, ValidationError | ConfigurationError):
        return ExitCode.VALIDATION_ERROR
    if isinstance(error, NotFoundError):
        return ExitCode.NOT_FOUND
    if isinstance(error, ConflictError):
        return ExitCode.CONFLICT
    if isinstance(error, OperationTimeoutError):
        return ExitCode.TIMEOUT
    if isinstance(error, RuntimeExecutionError):
        return ExitCode.RUNTIME_ERROR
    return ExitCode.RUNTIME_ERROR
