from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from apps.cli.exit_codes import ExitCode
from apps.cli.main import app
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.infra.models import AttemptModel, Base, JobModel, WorkerModel
from libs.services.database import SessionManager


runner = CliRunner()


def _seed_jobs(instance_root: Path) -> None:
    database_path = instance_root / "xqueue.db"
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 20, 30, tzinfo=UTC)
    log_root = instance_root / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    failed_stderr_path = log_root / "job-failed.stderr.log"
    failed_stderr_path.write_text("line-1\nline-2\nline-3\n")

    with SessionManager(session_factory).transaction() as session:
        session.add(
            WorkerModel(
                id="worker-1",
                state="active",
                queues=["agent"],
                heartbeat_at=now + timedelta(seconds=2),
                started_at=now + timedelta(seconds=2),
                process_id=12345,
                concurrency=1,
            )
        )
        session.add_all(
            [
                JobModel(
                    id="job-queued",
                    queue="agent",
                    command="echo queued",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="queued",
                ),
                JobModel(
                    id="job-failed",
                    queue="agent",
                    command="echo failed",
                    shell=True,
                    priority=20,
                    created_at=now + timedelta(seconds=1),
                    available_at=now + timedelta(seconds=5),
                    state="failed",
                    attempt_count=1,
                    last_exit_code=1,
                    last_error="boom",
                    created_by="tester",
                ),
                JobModel(
                    id="job-running",
                    queue="agent",
                    command="sleep 30",
                    shell=True,
                    priority=30,
                    created_at=now + timedelta(seconds=2),
                    available_at=now + timedelta(seconds=2),
                    state="running",
                    worker_id="worker-1",
                ),
            ]
        )
        session.add(
            AttemptModel(
                job_id="job-failed",
                attempt_number=1,
                state="failed",
                started_at=now + timedelta(seconds=1),
                finished_at=now + timedelta(seconds=2),
                exit_code=1,
                error="boom",
                stderr_path=str(failed_stderr_path),
            )
        )

    engine.dispose()


def test_jobs_list_returns_json_list_response(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            [
                "jobs",
                "list",
                "--queue",
                "agent",
                "--state",
                "failed",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert list(payload.keys()) == ["items", "meta"]
        assert len(payload["items"]) == 1
        assert payload["items"][0]["id"] == "job-failed"
        assert payload["items"][0]["state"] == "failed"


def test_jobs_list_supports_time_filters_and_explicit_sort(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            [
                "jobs",
                "list",
                "--queue",
                "agent",
                "--created-after",
                "2026-03-22T20:30:00.500000Z",
                "--available-before",
                "2026-03-22T20:30:04Z",
                "--sort",
                "available-desc",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert [item["id"] for item in payload["items"]] == ["job-running"]


def test_jobs_show_returns_json_detail_response(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            [
                "jobs",
                "show",
                "job-failed",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert list(payload.keys()) == ["item"]
        assert payload["item"]["id"] == "job-failed"
        assert payload["item"]["attempts"][0]["stderr_path"].endswith("job-failed.stderr.log")


def test_jobs_show_returns_structured_not_found_error(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            [
                "jobs",
                "show",
                "missing-job",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == int(ExitCode.NOT_FOUND)
        payload = json.loads(result.stdout)

        assert payload["ok"] is False
        assert payload["error"]["code"] == "not_found"
        assert payload["error"]["details"] == {"job_id": "missing-job"}


def test_jobs_cancel_returns_mutation_response_for_queued_job(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            [
                "jobs",
                "cancel",
                "job-queued",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert payload["ok"] is True
        assert payload["item"]["id"] == "job-queued"
        assert payload["item"]["state"] == "canceled"
        assert payload["item"]["cancel_requested_at"] is not None


def test_jobs_retry_returns_mutation_response_for_failed_job(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            [
                "jobs",
                "retry",
                "job-failed",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert payload["ok"] is True
        assert payload["item"]["id"] == "job-failed"
        assert payload["item"]["state"] == "queued"
        assert len(payload["item"]["attempts"]) == 1
        assert payload["item"]["last_error"] is None
        assert payload["item"]["last_exit_code"] is None


def test_jobs_retry_returns_conflict_for_non_terminal_job(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            [
                "jobs",
                "retry",
                "job-queued",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == int(ExitCode.CONFLICT)
        payload = json.loads(result.stdout)

        assert payload["ok"] is False
        assert payload["error"]["code"] == "conflict"


def test_jobs_purge_deletes_only_queued_jobs_for_queue(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            [
                "jobs",
                "purge",
                "--queue",
                "agent",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert payload["ok"] is True
        assert payload["item"]["queue"] == "agent"
        assert payload["item"]["deleted_count"] == 1


def test_jobs_delete_returns_mutation_response_and_removes_logs(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            [
                "jobs",
                "delete",
                "job-failed",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert payload["ok"] is True
        assert payload["item"]["job_id"] == "job-failed"
        assert payload["item"]["deleted_state"] == "failed"
        assert payload["item"]["deleted_attempt_count"] == 1
        assert len(payload["item"]["deleted_log_paths"]) == 1
        assert not Path(payload["item"]["deleted_log_paths"][0]).exists()


def test_jobs_delete_returns_conflict_for_running_job(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            [
                "jobs",
                "delete",
                "job-running",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == int(ExitCode.CONFLICT)
        payload = json.loads(result.stdout)

        assert payload["ok"] is False
        assert payload["error"]["code"] == "conflict"
        assert payload["error"]["details"] == {"job_id": "job-running", "state": "running"}


def test_jobs_tail_returns_json_detail_response_for_latest_attempt_stderr(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            [
                "jobs",
                "tail",
                "job-failed",
                "--lines",
                "2",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert payload["item"]["job_id"] == "job-failed"
        assert payload["item"]["attempt_number"] == 1
        assert payload["item"]["stream"] == "stderr"
        assert payload["item"]["lines"] == ["line-2", "line-3"]
        assert payload["item"]["truncated"] is True
