from __future__ import annotations

from pathlib import Path

from xqueue.workers.execution_action import RunShellCommandAction
from xqueue.workers.models import ShellExecutionRequest
from xqueue.workers.process import CommandExecutionService


def test_run_shell_command_action_executes_and_returns_log_paths(tmp_path: Path) -> None:
    action = RunShellCommandAction(tmp_path / "logs", CommandExecutionService())

    result = action(
        job_id="job-abc",
        attempt_number=2,
        request=ShellExecutionRequest(command="printf 'from action\\n'"),
    )

    assert result.exit_code == 0
    assert result.stdout_path.endswith("logs/jobs/job-abc/attempt-0002.stdout.log")
    assert Path(result.stdout_path).read_text() == "from action\n"
    assert Path(result.stderr_path).read_text() == ""
