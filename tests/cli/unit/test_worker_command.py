from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from typer.testing import CliRunner

from xqueue_cli.main import app
from xqueue_libs.infra.database import create_session_factory, create_sqlite_engine
from xqueue_libs.infra.models import Base, JobModel
from xqueue_libs.services.database import SessionManager


runner = CliRunner()


def _seed_job(database_path: Path) -> None:
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime.now(UTC) - timedelta(seconds=5)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-cli",
                queue="agent",
                command="echo cli",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="queued",
            )
        )

    engine.dispose()


def test_worker_run_claims_job_and_returns_json_detail(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        database_path = instance / "xqueue.db"
        _seed_job(database_path)

        result = runner.invoke(
            app,
            [
                "worker",
                "run",
                "--worker-id",
                "worker-cli",
                "--queue",
                "agent",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert list(payload.keys()) == ["item"]
        assert payload["item"]["worker"]["id"] == "worker-cli"
        assert payload["item"]["worker"]["state"] == "active"
        assert payload["item"]["claimed_job"]["id"] == "job-cli"
        assert payload["item"]["claimed_job"]["state"] == "running"

        engine = create_sqlite_engine(database_path)
        with engine.connect() as connection:
            job_row = connection.execute(
                text("SELECT state, worker_id FROM jobs WHERE id = :job_id"),
                {"job_id": "job-cli"},
            ).one()
            worker_row = connection.execute(
                text("SELECT state FROM workers WHERE id = :worker_id"),
                {"worker_id": "worker-cli"},
            ).one()
        engine.dispose()

        assert job_row.state == "running"
        assert job_row.worker_id == "worker-cli"
        assert worker_row.state == "active"


def test_worker_direct_invocation_alias_claims_job_and_returns_json_detail(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        database_path = instance / "xqueue.db"
        _seed_job(database_path)

        result = runner.invoke(
            app,
            [
                "worker",
                "--worker-id",
                "worker-cli",
                "--queue",
                "agent",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert list(payload.keys()) == ["item"]
        assert payload["item"]["worker"]["id"] == "worker-cli"
        assert payload["item"]["claimed_job"]["id"] == "job-cli"
        assert payload["item"]["claimed_job"]["state"] == "running"


def test_worker_run_execute_claimed_completes_job_and_records_attempt(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        database_path = instance / "xqueue.db"
        _seed_job(database_path)

        result = runner.invoke(
            app,
            [
                "worker",
                "run",
                "--worker-id",
                "worker-cli",
                "--queue",
                "agent",
                "--execute-claimed",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert payload["item"]["worker"]["id"] == "worker-cli"
        assert payload["item"]["claimed_job"]["id"] == "job-cli"
        assert payload["item"]["claimed_job"]["state"] == "succeeded"
        assert payload["item"]["claimed_job"]["attempts"][0]["state"] == "succeeded"

        engine = create_sqlite_engine(database_path)
        with engine.connect() as connection:
            job_row = connection.execute(
                text("SELECT state, attempt_count, worker_id FROM jobs WHERE id = :job_id"),
                {"job_id": "job-cli"},
            ).one()
            attempt_row = connection.execute(
                text("SELECT state, stdout_path, stderr_path FROM attempts WHERE job_id = :job_id"),
                {"job_id": "job-cli"},
            ).one()
        engine.dispose()

        assert job_row.state == "succeeded"
        assert job_row.attempt_count == 1
        assert job_row.worker_id is None
        assert Path(attempt_row.stdout_path).read_text() == "cli\n"
        assert Path(attempt_row.stderr_path).read_text() == ""


def test_worker_run_continuous_execute_claimed_with_max_polls_exits_after_one_poll(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        database_path = instance / "xqueue.db"
        _seed_job(database_path)

        result = runner.invoke(
            app,
            [
                "worker",
                "run",
                "--worker-id",
                "worker-cli",
                "--queue",
                "agent",
                "--continuous",
                "--execute-claimed",
                "--max-polls",
                "1",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["item"]["worker"]["id"] == "worker-cli"
        assert payload["item"]["claimed_job"]["id"] == "job-cli"
        assert payload["item"]["claimed_job"]["state"] == "succeeded"

        engine = create_sqlite_engine(database_path)
        with engine.connect() as connection:
            job_row = connection.execute(
                text("SELECT state, attempt_count, worker_id FROM jobs WHERE id = :job_id"),
                {"job_id": "job-cli"},
            ).one()
            attempt_count = connection.execute(
                text("SELECT COUNT(*) FROM attempts WHERE job_id = :job_id"),
                {"job_id": "job-cli"},
            ).scalar_one()
        engine.dispose()

        assert job_row.state == "succeeded"
        assert job_row.attempt_count == 1
        assert job_row.worker_id is None
        assert attempt_count == 1


def test_worker_rejects_concurrency_greater_than_one_without_continuous_mode(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("instance").mkdir(exist_ok=True)

        result = runner.invoke(
            app,
            [
                "worker",
                "--queue",
                "agent",
                "--concurrency",
                "2",
                "--execute-claimed",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "validation_error"
        assert "only supported with --continuous and --execute-claimed" in payload["error"]["message"]


def test_worker_rejects_concurrency_greater_than_one_without_execute_claimed(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("instance").mkdir(exist_ok=True)

        result = runner.invoke(
            app,
            [
                "worker",
                "--queue",
                "agent",
                "--concurrency",
                "2",
                "--continuous",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "validation_error"
        assert payload["error"]["details"] == {
            "concurrency": 2,
            "continuous": True,
            "execute_claimed": False,
        }
