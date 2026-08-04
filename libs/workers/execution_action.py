"""Typed direct execution action owned by workers."""

from __future__ import annotations

from pathlib import Path

from xqueue.runtime.action_logging import log_action
from xqueue.workers.models import ProcessExecutionResult, ShellExecutionRequest
from xqueue.workers.ports import ProcessRunnerPort


class RunShellCommandAction:
    """Run one shell command and capture stdout/stderr to managed files."""

    def __init__(
        self,
        log_root: Path,
        execution_service: ProcessRunnerPort,
        *,
        cancel_grace_period_seconds: int = 10,
    ) -> None:
        self._log_root = log_root
        self._execution_service = execution_service
        self._cancel_grace_period_seconds = cancel_grace_period_seconds

    @log_action(
        "run_shell_command",
        context_getter=lambda self, *, job_id, attempt_number, request: {
            "job_id": job_id,
            "attempt_number": attempt_number,
            "has_cwd": request.cwd is not None,
            "timeout_seconds": request.timeout_seconds,
        },
        result_getter=lambda result: {
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "canceled": result.canceled,
        },
    )
    def __call__(
        self,
        *,
        job_id: str,
        attempt_number: int,
        request: ShellExecutionRequest,
    ) -> ProcessExecutionResult:
        log_paths = self._execution_service.build_attempt_log_paths(
            log_root=self._log_root,
            job_id=job_id,
            attempt_number=attempt_number,
        )
        return self._execution_service.run(
            request=request,
            log_paths=log_paths,
            cancel_grace_period_seconds=self._cancel_grace_period_seconds,
        )
