"""Shared output selection and rendering for CLI commands."""

from __future__ import annotations

import json
from enum import StrEnum
from io import StringIO
from typing import Any
from typing import NoReturn

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.pretty import Pretty

from libs.services.axi_contracts import get_command_contract, parse_fields_csv, validate_requested_fields
from libs.domain.responses import ErrorDetail, ErrorResponse, PayloadConvertible
from libs.services.toon_renderer import render_toon


class OutputFormat(StrEnum):
    TOON = "toon"
    JSONL = "jsonl"
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


def _to_payload(value: Any) -> Any:
    if isinstance(value, PayloadConvertible):
        return value.to_payload()
    return to_jsonable(value)


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return to_jsonable(value)


def _jsonl_items(value: Any) -> list[Any] | None:
    if isinstance(value, PayloadConvertible):
        return value.jsonl_items()
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return None


def _render_text(value: Any) -> str:
    buffer = StringIO()
    console = Console(file=buffer, stderr=False, force_terminal=False, color_system=None)
    console.print(Pretty(_to_payload(value)))
    return buffer.getvalue().rstrip("\n")


def _resolve_output(ctx: typer.Context, local_output: OutputFormat | None) -> OutputFormat:
    if local_output is not None:
        return local_output
    current = ctx
    while current is not None:
        obj = getattr(current, "obj", None)
        if isinstance(obj, dict) and isinstance(obj.get("output"), OutputFormat):
            return obj["output"]
        output_param = current.params.get("output") if getattr(current, "params", None) else None
        if isinstance(output_param, OutputFormat):
            return output_param
        current = current.parent
    return OutputFormat.TOON


def _resolve_nested_fields(
    requested: tuple[str, ...],
    *,
    key: str | None,
    allowed_fields: tuple[str, ...],
    default_fields: tuple[str, ...],
) -> tuple[str, ...]:
    if not allowed_fields:
        return ()
    if not requested:
        return default_fields or allowed_fields

    resolved: dict[str, None] = {}
    prefix = f"{key}." if key else None
    requested_set = set(requested)

    for field in allowed_fields:
        if field in requested_set:
            resolved.setdefault(field, None)
        if prefix is not None and f"{prefix}{field}" in requested_set:
            resolved.setdefault(field, None)

    return tuple(resolved)


def _resolve_top_fields(
    payload: dict[str, Any],
    *,
    contract,
    requested: tuple[str, ...],
    selected_row_fields: tuple[str, ...],
    selected_item_fields: tuple[str, ...],
) -> tuple[str, ...]:
    if not requested:
        return tuple(field for field in contract.default_fields if field in payload)

    requested_set = set(requested)
    resolved: dict[str, None] = {}

    for field in contract.allowed_fields:
        if field in payload and field in requested_set:
            resolved.setdefault(field, None)

    if contract.list_key and selected_row_fields and contract.list_key in payload:
        resolved.setdefault(contract.list_key, None)
    if contract.item_key and selected_item_fields and contract.item_key in payload:
        resolved.setdefault(contract.item_key, None)

    return tuple(resolved)


def _select_payload(payload: Any, *, contract, requested: tuple[str, ...]) -> Any:
    if not isinstance(payload, dict):
        return payload

    selected_row_fields = _resolve_nested_fields(
        requested,
        key=contract.list_key,
        allowed_fields=contract.list_row_fields,
        default_fields=contract.default_row_fields,
    )
    selected_item_fields = _resolve_nested_fields(
        requested,
        key=contract.item_key,
        allowed_fields=contract.item_fields,
        default_fields=contract.default_item_fields,
    )
    selected_top_fields = _resolve_top_fields(
        payload,
        contract=contract,
        requested=requested,
        selected_row_fields=selected_row_fields,
        selected_item_fields=selected_item_fields,
    )

    selected: dict[str, Any] = {}
    for field in selected_top_fields:
        value = payload[field]
        if field == contract.list_key and isinstance(value, list) and selected_row_fields:
            selected[field] = [
                {row_field: item[row_field] for row_field in selected_row_fields if row_field in item}
                if isinstance(item, dict)
                else item
                for item in value
            ]
            continue
        if field == contract.item_key and isinstance(value, dict) and selected_item_fields:
            selected[field] = {
                item_field: value[item_field]
                for item_field in selected_item_fields
                if item_field in value
            }
            continue
        selected[field] = value

    return selected


class Output:
    """Pre-configured output surface for one command invocation."""

    def __init__(
        self,
        ctx: typer.Context,
        contract_name: str,
        local_output: OutputFormat | None = None,
        console: Console | None = None,
    ) -> None:
        self._fmt = _resolve_output(ctx, local_output)
        self._contract = get_command_contract(contract_name)
        self._console = console or Console(stderr=False)
        current = ctx
        fields_csv = None
        self._full = False
        while current is not None:
            obj = getattr(current, "obj", None)
            if isinstance(obj, dict):
                fields_csv = obj.get("fields", fields_csv)
                self._full = bool(obj.get("full", self._full))
                break
            current = current.parent
        self._requested_fields = validate_requested_fields(self._contract, parse_fields_csv(fields_csv))

    @property
    def fmt(self) -> OutputFormat:
        return self._fmt

    @property
    def contract_name(self) -> str:
        return self._contract.name

    @property
    def contract(self):
        return self._contract

    @property
    def full(self) -> bool:
        return self._full

    @property
    def requested_fields(self) -> tuple[str, ...]:
        return self._requested_fields

    def print(self, response: PayloadConvertible | Any) -> None:
        """Render and emit a response to stdout."""
        if self._fmt is OutputFormat.TEXT:
            self._console.print(Pretty(_to_payload(response)))
            return
        typer.echo(self.render(response))

    def render(self, response: PayloadConvertible | Any) -> str:
        """Render a response to string without writing to stdout."""
        payload = _to_payload(response)

        if self._fmt is OutputFormat.TOON:
            return render_toon(_select_payload(payload, contract=self._contract, requested=self._requested_fields))
        if self._fmt is OutputFormat.JSON:
            selected = payload if not self._requested_fields else _select_payload(
                payload,
                contract=self._contract,
                requested=self._requested_fields,
            )
            return json.dumps(selected, indent=2, default=_json_default)
        if self._fmt is OutputFormat.JSONL:
            items = _jsonl_items(response)
            if items:
                return "\n".join(json.dumps(to_jsonable(item), default=_json_default) for item in items)
            return json.dumps(payload, default=_json_default)
        return _render_text(payload)

    def error(
        self,
        message: str,
        *,
        code: str = "runtime_error",
        details: dict[str, Any] | None = None,
        hints: list[str] | None = None,
        exit_code: int = 1,
    ) -> NoReturn:
        """Render a structured error payload and exit."""
        del hints
        response = ErrorResponse(
            error=ErrorDetail(
                code=code,
                message=message,
                details=details or {},
            )
        )
        saved_contract = self._contract
        saved_requested_fields = self._requested_fields
        self._contract = get_command_contract("error")
        self._requested_fields = ()
        try:
            self.print(response)
        finally:
            self._contract = saved_contract
            self._requested_fields = saved_requested_fields
        raise typer.Exit(code=exit_code)
