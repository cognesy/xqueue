"""Shared output selection and rendering for CLI commands."""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from rich.console import Console
from rich.pretty import Pretty

from libs.domain.responses import ErrorResponse


class OutputFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


def to_jsonable(value: Any) -> Any:
    """Convert supported result types into JSON-serializable data."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def emit_result(value: Any, output_format: OutputFormat, console: Console | None = None) -> None:
    """Render a successful command result using the selected format."""
    payload = to_jsonable(value)

    if output_format is OutputFormat.JSON:
        stream = sys.stdout if console is None else console.file
        stream.write(json.dumps(payload, indent=2))
        stream.write("\n")
        stream.flush()
        return

    console = console or Console()
    console.print(Pretty(payload))


def emit_error(error: ErrorResponse, output_format: OutputFormat, console: Console | None = None) -> None:
    """Render a failure payload using the selected format."""
    emit_result(error, output_format=output_format, console=console)
