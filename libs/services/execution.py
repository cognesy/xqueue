"""Subprocess execution and attempt log capture services."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from libs.domain.errors import ValidationError
from libs.domain.models import AttemptLogPaths, ProcessExecutionResult, ShellExecutionRequest
from libs.services.operation_logs import JobOperationLogService


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class CommandExecutionService:
    """Run shell commands in their own process groups and capture output to files."""

    def __init__(self, operation_logs: JobOperationLogService | None = None) -> None:
        self._operation_logs = operation_logs or JobOperationLogService()

    def build_attempt_log_paths(self, *, log_root: Path, job_id: str, attempt_number: int) -> AttemptLogPaths:
        job_root = log_root / "jobs" / job_id
        return AttemptLogPaths(
            stdout_path=str(job_root / f"attempt-{attempt_number:04d}.stdout.log"),
            stderr_path=str(job_root / f"attempt-{attempt_number:04d}.stderr.log"),
            event_log_path=self._operation_logs.build_attempt_event_log_path(
                log_root=log_root,
                job_id=job_id,
                attempt_number=attempt_number,
            ),
        )

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
        on_heartbeat: Callable[[], None] | None = None,
    ) -> ProcessExecutionResult:
        if not request.shell:
            raise ValidationError("shell execution is required in v1")

        stdout_path = Path(log_paths.stdout_path)
        stderr_path = Path(log_paths.stderr_path)
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        if request.env:
            env.update(request.env)

        started_at = utc_now()
        with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
            try:
                process = subprocess.Popen(
                    ["/bin/sh", "-lc", request.command],
                    cwd=request.cwd,
                    env=env,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    start_new_session=True,
                )
            except OSError as exc:
                stderr_handle.write(f"{exc}\n".encode())
                stderr_handle.flush()
                finished_at = utc_now()
                return ProcessExecutionResult(
                    command=request.command,
                    started_at=started_at,
                    finished_at=finished_at,
                    exit_code=None,
                    canceled=False,
                    timed_out=False,
                    cancellation_reason=None,
                    stdout_path=str(stdout_path),
                    stderr_path=str(stderr_path),
                )
            process_group_id = os.getpgid(process.pid)
            deadline = None if request.timeout_seconds is None else time.monotonic() + request.timeout_seconds
            next_heartbeat_at = None
            if on_heartbeat is not None and heartbeat_interval_seconds is not None:
                next_heartbeat_at = time.monotonic() + heartbeat_interval_seconds
            canceled = False
            timed_out = False
            exit_code: int | None = None

            while True:
                exit_code = process.poll()
                if exit_code is not None:
                    break
                if should_cancel is not None and should_cancel():
                    canceled = True
                    self._terminate_process_group(
                        process=process,
                        process_group_id=process_group_id,
                        grace_period_seconds=cancel_grace_period_seconds,
                    )
                    exit_code = process.wait()
                    break
                if deadline is not None and time.monotonic() >= deadline:
                    timed_out = True
                    self._terminate_process_group(
                        process=process,
                        process_group_id=process_group_id,
                        grace_period_seconds=cancel_grace_period_seconds,
                    )
                    exit_code = process.wait()
                    break
                if on_heartbeat is not None and next_heartbeat_at is not None and time.monotonic() >= next_heartbeat_at:
                    on_heartbeat()
                    next_heartbeat_at = time.monotonic() + heartbeat_interval_seconds
                time.sleep(poll_interval_seconds)

        finished_at = utc_now()
        return ProcessExecutionResult(
            command=request.command,
            process_id=process.pid,
            process_group_id=process_group_id,
            started_at=started_at,
            finished_at=finished_at,
            exit_code=exit_code,
            canceled=canceled,
            timed_out=timed_out,
            cancellation_reason=cancellation_reason if canceled else None,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )

    def _terminate_process_group(
        self,
        *,
        process: subprocess.Popen[bytes],
        process_group_id: int,
        grace_period_seconds: int,
    ) -> None:
        if process.poll() is not None:
            return

        try:
            os.killpg(process_group_id, signal.SIGTERM)
        except ProcessLookupError:
            return

        deadline = time.monotonic() + grace_period_seconds
        while time.monotonic() < deadline:
            if process.poll() is not None:
                return
            time.sleep(0.1)

        if process.poll() is not None:
            return

        try:
            os.killpg(process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            return
