"""Narrow contracts for worker orchestration adapters."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from xqueue.workers.models import AttemptLogPaths, ProcessExecutionResult, ShellExecutionRequest


class ProcessRunnerPort(Protocol):
    """Run one command in an independently terminable process group.

    Worker use cases annotate their execution dependency with this protocol, so
    the seam is type-checked rather than merely described.
    """

    def build_attempt_log_paths(self, *, log_root: Path, job_id: str, attempt_number: int) -> AttemptLogPaths: ...

    def run(
        self,
        *,
        request: ShellExecutionRequest,
        log_paths: AttemptLogPaths,
        cancel_grace_period_seconds: int = 10,
        should_cancel: Callable[[], bool] | None = None,
        cancellation_reason: str = "operator_requested",
        poll_interval_seconds: float = 0.1,
        heartbeat_interval_seconds: float | None = None,
        # The callback's return value is ignored; callers may return anything.
        on_heartbeat: Callable[[], object] | None = None,
    ) -> ProcessExecutionResult: ...
