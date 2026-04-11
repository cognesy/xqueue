"""Shared CLI execution helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from apps.cli.exit_codes import map_error_to_exit_code
from apps.cli.output import Output
from libs.domain.errors import XqueueError


T = TypeVar("T")


def run_action(fn: Callable[[], T], *, out: Output) -> None:
    """Execute an action, render its result, and map failures to exit codes."""
    try:
        out.print(fn())
    except XqueueError as exc:
        out.error(
            exc.message,
            code=exc.code,
            details=exc.details,
            exit_code=int(map_error_to_exit_code(exc)),
        )
