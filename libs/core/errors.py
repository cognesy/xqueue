"""Errors shared by the public client and capability core."""

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


class StateStoreUnavailableError(XqueueError):
    """The durable state store is missing, unreadable, or has no schema yet."""

    code = "state_store_unavailable"


class RuntimeExecutionError(XqueueError):
    code = "runtime_error"


class OperationTimeoutError(XqueueError):
    code = "timeout"


class InvalidWorkspaceError(XqueueError):
    """A directory looks like a workspace but its marker does not check out.

    Distinct from "no workspace here", which is not an error: it selects the
    home instance. This is raised when a marker exists and is unreadable,
    belongs to another product, or declares a schema this build cannot honour.
    Falling back silently in that case would operate on the wrong state.
    """

    code = "invalid_workspace"


class ConfigurationError(XqueueError):
    """Configuration could not be composed or did not validate."""

    code = "configuration_error"


class XqueueClosedError(RuntimeError):
    """Raised when an operation uses a closed xqueue client."""
