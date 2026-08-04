from __future__ import annotations

from pathlib import Path

from xqueue.jobs.logs import JobLogService


def test_tail_returns_last_lines_and_truncation_flag(tmp_path: Path) -> None:
    path = tmp_path / "attempt.stderr.log"
    path.write_text("one\ntwo\nthree\n")

    lines, truncated = JobLogService().tail(path=str(path), lines=2)

    assert lines == ["two", "three"]
    assert truncated is True


def test_delete_paths_removes_existing_log_files(tmp_path: Path) -> None:
    stdout_path = tmp_path / "job" / "attempt.stdout.log"
    stderr_path = tmp_path / "job" / "attempt.stderr.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text("stdout\n")
    stderr_path.write_text("stderr\n")

    deleted_paths = JobLogService().delete_paths(paths=[str(stdout_path), str(stderr_path)])

    assert sorted(deleted_paths) == sorted([str(stdout_path), str(stderr_path)])
    assert not stdout_path.exists()
    assert not stderr_path.exists()
    assert not stdout_path.parent.exists()
