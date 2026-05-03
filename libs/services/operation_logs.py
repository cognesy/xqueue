"""Structured operational event logs for job attempts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class JobOperationLogService:
    """Append concise JSONL operation events beside raw attempt output logs."""

    def build_attempt_event_log_path(self, *, log_root: Path, job_id: str, attempt_number: int) -> str:
        return str(log_root / "jobs" / job_id / f"attempt-{attempt_number:04d}.events.jsonl")

    def append(
        self,
        *,
        path: str,
        event: str,
        job_id: str,
        queue: str,
        worker_id: str,
        attempt_id: int | None = None,
        attempt_number: int | None = None,
        command: str | None = None,
        cwd: str | None = None,
        pid: int | None = None,
        exit_code: int | None = None,
        outcome: str | None = None,
        duration_seconds: float | None = None,
        stdout_path: str | None = None,
        stderr_path: str | None = None,
        correlation: dict[str, str] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        log_path = Path(path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": self._format_timestamp(timestamp or utc_now()),
            "event": event,
            "job_id": job_id,
            "queue": queue,
            "worker_id": worker_id,
            "attempt_id": attempt_id,
            "attempt_number": attempt_number,
            "command": command,
            "cwd": cwd,
            "pid": pid,
            "exit_code": exit_code,
            "outcome": outcome,
            "duration_seconds": duration_seconds,
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
            "event_log_path": str(log_path),
            "correlation": correlation or {},
        }
        compact = {key: value for key, value in payload.items() if value is not None}
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(compact, sort_keys=True, separators=(",", ":")) + "\n")

    def correlation_from_env(self, env: dict[str, Any] | None) -> dict[str, str]:
        if not env:
            return {}
        return {
            key.lower(): str(value)
            for key, value in sorted(env.items())
            if key.startswith("XPM_") or key.startswith("XCRON_") or key.startswith("XQUEUE_")
        }

    def _format_timestamp(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
