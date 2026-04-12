"""Compact tmux-pane renderer for xqueue CLI output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _format_value(value: Any) -> str:
    """Format a single value for tmux display."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return str(len(value))
    if isinstance(value, dict):
        return str(len(value))
    return str(value)


def _render_flat(data: Mapping[str, Any]) -> str:
    """Render a flat dict as key=value pairs."""
    parts: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                parts.append(f"{nested_key}={_format_value(nested_value)}")
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            parts.append(f"{key}={len(value)}")
        else:
            parts.append(f"{key}={_format_value(value)}")
    return " ".join(parts)


def _render_table(items: list[Any]) -> str:
    """Render a list of dicts as aligned columns."""
    if not items:
        return "0 items"
    if not isinstance(items[0], dict):
        return "\n".join(str(item) for item in items)

    headers = list(items[0].keys())
    col_widths = {h: len(h) for h in headers}
    rows: list[dict[str, str]] = []
    for item in items:
        row = {}
        for h in headers:
            cell = _format_value(item.get(h))
            row[h] = cell
            col_widths[h] = max(col_widths[h], len(cell))
        rows.append(row)

    lines: list[str] = []
    for row in rows:
        parts = [row[h].ljust(col_widths[h]) for h in headers]
        lines.append("  ".join(parts).rstrip())
    return "\n".join(lines)


def render_tmux(payload: Any) -> str:
    """Render a payload as compact tmux-pane output.

    - Detail/mutation responses: flattened key=value on one line
    - List responses: one row per item, aligned columns
    - Error responses: error code and message
    """
    if not isinstance(payload, Mapping):
        return str(payload)

    # Error response
    if "ok" in payload and payload.get("ok") is False and "error" in payload:
        error = payload["error"]
        if isinstance(error, dict):
            return f"ERR {error.get('code', 'unknown')}: {error.get('message', '')}"
        return f"ERR: {error}"

    # List response — render items as table
    if "items" in payload and isinstance(payload["items"], list):
        items = payload["items"]
        meta = payload.get("meta")
        header = f"{len(items)} items"
        if meta and isinstance(meta, dict) and meta.get("total") is not None:
            header = f"{len(items)}/{meta['total']} items"
        if not items:
            return header
        return f"{header}\n{_render_table(items)}"

    # Mutation response — skip ok=true, render item
    if "ok" in payload and payload.get("ok") is True and "item" in payload:
        item = payload["item"]
        if isinstance(item, dict):
            return _render_flat(item)
        return str(item)

    # Detail response — render item inline
    if "item" in payload and len(payload) == 1:
        item = payload["item"]
        if isinstance(item, dict):
            if "output_status" in item and "stdout" in item and "stderr" in item:
                return _render_job_pane(item)
            return _render_flat(item)
        return str(item)

    # Fallback: flat render
    return _render_flat(payload)


def _render_job_pane(item: Mapping[str, Any]) -> str:
    job_id = str(item.get("id", "unknown"))
    lines = [
        (
            f"job {job_id[:8]} | {item.get('state', 'unknown')} | queue {item.get('queue', 'unknown')} | "
            f"attempt {item.get('attempt_number', '-')} | elapsed {item.get('elapsed_seconds', '-')}s"
        ),
        f"worker {item.get('worker_id') or '-'} | process {item.get('process_status', 'unknown')}",
        f"output {item.get('output_status', 'unknown')}",
    ]
    for stream in ("stdout", "stderr"):
        value = item.get(stream)
        if isinstance(value, Mapping):
            lines.append(
                f"{stream}: {value.get('size_bytes', '-') or 0}B | modified {value.get('modified_at') or '-'} | {value.get('path') or '-'}"
            )
    return "\n".join(lines)


__all__ = ["render_tmux"]
