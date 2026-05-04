from __future__ import annotations

import time
from pathlib import Path

from xqueue_libs.domain.models import ShellExecutionRequest
from xqueue_libs.services.execution import CommandExecutionService


def test_build_attempt_log_paths_is_deterministic(tmp_path: Path) -> None:
    service = CommandExecutionService()

    paths = service.build_attempt_log_paths(
        log_root=tmp_path / "logs",
        job_id="job-123",
        attempt_number=7,
    )

    assert paths.stdout_path.endswith("logs/jobs/job-123/attempt-0007.stdout.log")
    assert paths.stderr_path.endswith("logs/jobs/job-123/attempt-0007.stderr.log")


def test_run_captures_stdout_and_stderr_to_files(tmp_path: Path) -> None:
    service = CommandExecutionService()
    log_paths = service.build_attempt_log_paths(
        log_root=tmp_path / "logs",
        job_id="job-123",
        attempt_number=1,
    )

    result = service.run(
        request=ShellExecutionRequest(
            command="printf 'hello\\n'; printf 'oops\\n' >&2",
            cwd=str(tmp_path),
            env={"XQUEUE_TEST_FLAG": "1"},
        ),
        log_paths=log_paths,
    )

    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.process_id > 0
    assert result.process_group_id > 0
    assert Path(result.stdout_path).read_text() == "hello\n"
    assert Path(result.stderr_path).read_text() == "oops\n"


def test_run_invokes_heartbeat_callback_while_process_is_active(tmp_path: Path) -> None:
    service = CommandExecutionService()
    log_paths = service.build_attempt_log_paths(
        log_root=tmp_path / "logs",
        job_id="job-heartbeat",
        attempt_number=1,
    )
    heartbeat_calls: list[float] = []

    result = service.run(
        request=ShellExecutionRequest(
            command="sleep 0.35",
            cwd=str(tmp_path),
        ),
        log_paths=log_paths,
        poll_interval_seconds=0.05,
        heartbeat_interval_seconds=0.1,
        on_heartbeat=lambda: heartbeat_calls.append(time.monotonic()),
    )

    assert result.exit_code == 0
    assert len(heartbeat_calls) >= 2
