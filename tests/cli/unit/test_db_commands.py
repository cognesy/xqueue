from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from apps.cli.exit_codes import ExitCode
from apps.cli.main import app
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.infra.models import AttemptModel, Base, EventModel, JobModel
from libs.services.database import SessionManager


runner = CliRunner()


def test_db_reset_workspace_instance_requires_yes(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app,
            [
                "db",
                "reset-workspace-instance",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == int(ExitCode.VALIDATION_ERROR)
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "validation_error"


def test_db_reset_workspace_instance_removes_runtime_artifacts_and_preserves_config(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        runtime = instance / "run"
        logs = instance / "logs"
        config_file = instance / "config.yaml"
        database_path = instance / "xqueue.db"

        runtime.mkdir(parents=True, exist_ok=True)
        logs.mkdir(parents=True, exist_ok=True)
        config_file.write_text("controller:\n  pools: {}\n")
        database_path.write_text("sqlite-data")
        (runtime / "controller.pid").write_text("123\n")
        (logs / "worker.log").write_text("hello\n")

        result = runner.invoke(
            app,
            [
                "db",
                "reset-workspace-instance",
                "--yes",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert payload["ok"] is True
        assert payload["item"]["config_file"].endswith("instance/config.yaml")
        assert payload["item"]["removed_paths"] == [
            str(database_path.resolve()),
            str(runtime.resolve()),
            str(logs.resolve()),
        ]
        assert str(database_path.resolve()) in payload["item"]["recreated_paths"]
        assert config_file.exists()
        assert database_path.exists()
        assert runtime.exists()
        assert logs.exists()
        assert list(runtime.iterdir()) == []
        assert list(logs.iterdir()) == []


def test_db_cleanup_retention_requires_yes(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            app,
            [
                "db",
                "cleanup-retention",
                "--older-than-hours",
                "24",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == int(ExitCode.VALIDATION_ERROR)
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "validation_error"


def test_db_cleanup_retention_requires_at_least_one_artifact_class(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("instance").mkdir(exist_ok=True)

        result = runner.invoke(
            app,
            [
                "db",
                "cleanup-retention",
                "--older-than-hours",
                "24",
                "--yes",
                "--no-attempts",
                "--no-events",
                "--no-logs",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == int(ExitCode.VALIDATION_ERROR)
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "validation_error"
        assert payload["error"]["message"] == "cleanup-retention requires at least one selected artifact class"


def test_db_cleanup_retention_prunes_old_attempts_events_and_logs(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        logs = instance / "logs"
        instance.mkdir(exist_ok=True)
        logs.mkdir(parents=True, exist_ok=True)

        database_path = instance / "xqueue.db"
        engine = create_sqlite_engine(database_path)
        Base.metadata.create_all(engine)
        session_factory = create_session_factory(engine)
        now = datetime.now(UTC)
        old_stdout = logs / "old.stdout.log"
        old_stderr = logs / "old.stderr.log"
        recent_stdout = logs / "recent.stdout.log"
        old_stdout.write_text("old\n")
        old_stderr.write_text("old\n")
        recent_stdout.write_text("recent\n")

        with SessionManager(session_factory).transaction() as session:
            session.add_all(
                [
                    JobModel(
                        id="job-old",
                        queue="agent",
                        command="echo old",
                        shell=True,
                        priority=10,
                        created_at=now - timedelta(days=3),
                        available_at=now - timedelta(days=3),
                        state="failed",
                        attempt_count=1,
                    ),
                    JobModel(
                        id="job-recent",
                        queue="agent",
                        command="echo recent",
                        shell=True,
                        priority=10,
                        created_at=now - timedelta(hours=2),
                        available_at=now - timedelta(hours=2),
                        state="failed",
                        attempt_count=1,
                    ),
                ]
            )
            session.add_all(
                [
                    AttemptModel(
                        job_id="job-old",
                        attempt_number=1,
                        state="failed",
                        started_at=now - timedelta(days=3),
                        finished_at=now - timedelta(days=3) + timedelta(minutes=1),
                        stdout_path=str(old_stdout),
                        stderr_path=str(old_stderr),
                    ),
                    AttemptModel(
                        job_id="job-recent",
                        attempt_number=1,
                        state="failed",
                        started_at=now - timedelta(hours=2),
                        finished_at=now - timedelta(hours=2) + timedelta(minutes=1),
                        stdout_path=str(recent_stdout),
                    ),
                ]
            )
            session.add(
                EventModel(
                    event_type="job.recovered_stale_lease",
                    created_at=now - timedelta(days=3),
                    payload={"job_id": "job-old"},
                    job_id="job-old",
                    attempt_id=1,
                )
            )

        result = runner.invoke(
            app,
            [
                "db",
                "cleanup-retention",
                "--older-than-hours",
                "24",
                "--yes",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert payload["ok"] is True
        assert payload["item"]["deleted_attempt_count"] == 1
        assert payload["item"]["deleted_event_count"] == 1
        assert payload["item"]["deleted_log_count"] == 2
        assert sorted(Path(path).name for path in payload["item"]["deleted_log_paths"]) == ["old.stderr.log", "old.stdout.log"]
        assert not old_stdout.exists()
        assert not old_stderr.exists()
        assert recent_stdout.exists()
