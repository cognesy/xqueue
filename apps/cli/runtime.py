"""Shared CLI execution helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import typer

from apps.cli.exit_codes import map_error_to_exit_code
from apps.cli.output import OutputFormat, emit_error, emit_result
from libs.domain.errors import XqueueError
from libs.domain.responses import ErrorDetail, ErrorResponse


T = TypeVar("T")


def run_action(fn: Callable[[], T], *, output_format: OutputFormat) -> None:
    """Execute an action, render its result, and map failures to exit codes."""
    try:
        emit_result(fn(), output_format=output_format)
    except XqueueError as exc:
        emit_error(
            ErrorResponse(
                error=ErrorDetail(
                    code=exc.code,
                    message=exc.message,
                    details=exc.details,
                )
            ),
            output_format=output_format,
        )
        raise typer.Exit(code=int(map_error_to_exit_code(exc))) from exc
