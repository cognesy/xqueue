"""CLI tests for jobs prune command."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from apps.cli.main import app
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.infra.models import AttemptModel, Base, EventModel, JobModel, WorkerModel
from libs.services.database import SessionManager


runner = CliRunner()


def _seed_jobs(instance_root: Path) -> None:
    database_path = instance_root / "xqueue.db"
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime.now(UTC)
    log_root = instance_root / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    failed_log = log_root / "job-failed.stderr.log"
    failed_log.write_text("error output\n")

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
                    created_at=now - timedelta(days=3),
                    available_at=now - timedelta(days=3),
                    state="failed",
                    attempt_count=1,
                    last_exit_code=1,
                    last_error="boom",
                ),
                JobModel(
                    id="job-succeeded",
                    queue="agent",
                    command="echo ok",
                    shell=True,
                    priority=10,
                    created_at=now - timedelta(days=5),
                    available_at=now - timedelta(days=5),
                    state="succeeded",
                    attempt_count=1,
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
                started_at=now - timedelta(days=3),
                finished_at=now - timedelta(days=3) + timedelta(minutes=1),
                exit_code=1,
                error="boom",
                stderr_path=str(failed_log),
            )
        )
        session.add(
            EventModel(
                event_type="job.enqueued",
                created_at=now - timedelta(days=3),
                payload={"job_id": "job-failed"},
                job_id="job-failed",
            )
        )
    engine.dispose()


def test_prune_dry_run_by_default(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            ["jobs", "prune", "--state", "failed", "--output", "json", "--workspace-instance"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["item"]["dry_run"] is True
        assert payload["item"]["matched_job_count"] == 1
        assert payload["item"]["deleted_job_count"] == 0


def test_prune_apply_deletes_failed_jobs(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            ["jobs", "prune", "--state", "failed", "--apply", "--output", "json", "--workspace-instance"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["item"]["dry_run"] is False
        assert payload["item"]["matched_job_count"] == 1
        assert payload["item"]["deleted_job_count"] == 1
        assert payload["item"]["deleted_attempt_count"] == 1
        assert payload["item"]["deleted_event_count"] == 1


def test_prune_apply_with_logs_deletes_log_files(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)
        log_path = instance / "logs" / "job-failed.stderr.log"
        assert log_path.exists()

        result = runner.invoke(
            app,
            ["jobs", "prune", "--state", "failed", "--logs", "--apply", "--output", "json", "--workspace-instance"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["item"]["deleted_log_count"] == 1
        assert not log_path.exists()


def test_prune_does_not_touch_running_jobs(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            ["jobs", "prune", "--apply", "--output", "json", "--workspace-instance"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        # Default prunes terminal states only — running and queued jobs untouched
        matched_ids = [j["id"] for j in payload["item"]["matched_jobs"]]
        assert "job-running" not in matched_ids
        assert "job-queued" not in matched_ids


def test_prune_with_older_than_filters_by_age(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            ["jobs", "prune", "--older-than", "4d", "--apply", "--output", "json", "--workspace-instance"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        # Only job-succeeded is older than 4 days
        assert payload["item"]["deleted_job_count"] == 1
        matched_ids = [j["id"] for j in payload["item"]["matched_jobs"]]
        assert "job-succeeded" in matched_ids
        assert "job-failed" not in matched_ids


def test_prune_terminal_state_filter(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            ["jobs", "prune", "--state", "terminal", "--output", "json", "--workspace-instance"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        # Should match both failed and succeeded
        assert payload["item"]["matched_job_count"] == 2
        matched_ids = [j["id"] for j in payload["item"]["matched_jobs"]]
        assert "job-failed" in matched_ids
        assert "job-succeeded" in matched_ids


def test_prune_tmux_output(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_jobs(instance)

        result = runner.invoke(
            app,
            ["jobs", "prune", "--state", "failed", "--output", "tmux", "--workspace-instance"],
        )

        assert result.exit_code == 0
        output = result.stdout.strip()
        assert "dry_run=yes" in output
        assert "matched_job_count=1" in output
