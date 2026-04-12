"""Persistent xqueue runtime metrics."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def resolve_metrics_path(env: dict[str, str] | None = None) -> Path:
    env_map = os.environ if env is None else env
    configured_home = env_map.get("XQUEUE_HOME")
    root = Path(configured_home).expanduser() if configured_home else Path.home() / ".xqueue"
    return (root / "metrics" / "metrics.json").resolve()


class MetricsService:
    """Store small operator-facing counters under XQUEUE_HOME."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or resolve_metrics_path()

    @property
    def path(self) -> Path:
        return self._path

    def show(self) -> dict[str, Any]:
        return {**self._read(), "path": str(self._path)}

    def reset(self) -> dict[str, Any]:
        previous = self._read()
        payload = self._empty_payload()
        self._write(payload)
        return {**payload, "path": str(self._path), "previous_counters": previous.get("counters", {})}

    def increment(self, counter: str, amount: int = 1) -> None:
        try:
            payload = self._read()
            counters = payload.setdefault("counters", {})
            counters[counter] = int(counters.get(counter, 0)) + amount
            payload["updated_at"] = utc_timestamp()
            self._write(payload)
        except Exception:
            return

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
        temp_path = self._path.with_suffix(f"{self._path.suffix}.{os.getpid()}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(self._path)

    def _empty_payload(self) -> dict[str, Any]:
        now = utc_timestamp()
        return {
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "counters": {},
        }
