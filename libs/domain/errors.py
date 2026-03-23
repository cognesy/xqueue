"""Domain-level exceptions and error codes."""

from __future__ import annotations

from typing import Any


class XqueueError(Exception):
    """Base application error surfaced to shells and automation."""

    code = "runtime_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(XqueueError):
    code = "validation_error"


class NotFoundError(XqueueError):
    code = "not_found"


class ConflictError(XqueueError):
    code = "conflict"


class RuntimeExecutionError(XqueueError):
    code = "runtime_error"


class OperationTimeoutError(XqueueError):
    code = "timeout"
