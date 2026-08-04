"""Persistent operator-facing runtime metrics."""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class MetricsService:
    """Store small operator-facing counters at one explicit path."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def show(self) -> dict[str, Any]:
        with self._lock:
            return {**self._read(), "path": str(self._path)}

    def reset(self) -> dict[str, Any]:
        with self._lock:
            previous = self._read()
            payload = self._empty_payload()
            self._write(payload)
        return {**payload, "path": str(self._path), "previous_counters": previous.get("counters", {})}

    def increment(self, counter: str, amount: int = 1) -> None:
        """Best-effort counter update; metrics never fail an operator action."""
        try:
            with self._lock:
                payload = self._read()
                counters = payload.setdefault("counters", {})
                counters[counter] = int(counters.get(counter, 0)) + amount
                payload["updated_at"] = utc_timestamp()
                self._write(payload)
        except OSError as exc:
            structlog.get_logger("xqueue.metrics").debug(
                "metrics.increment_failed",
                counter=counter,
                path=str(self._path),
                error=str(exc),
            )

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return self._empty_payload()
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty_payload()
        if not isinstance(payload, dict):
            return self._empty_payload()
        payload.setdefault("version", 1)
        payload.setdefault("created_at", utc_timestamp())
        payload.setdefault("updated_at", payload["created_at"])
        if not isinstance(payload.get("counters"), dict):
            payload["counters"] = {}
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Unique per writing process and thread: two writers must never share a
        # temp path, or one can publish a file the other is still writing.
        temp_path = self._path.with_suffix(f"{self._path.suffix}.{os.getpid()}.{uuid4().hex}.tmp")
        try:
            temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temp_path.replace(self._path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _empty_payload(self) -> dict[str, Any]:
        now = utc_timestamp()
        return {
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "counters": {},
        }
