"""CLI tests for --output tmux on controller status, health, and jobs list."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from apps.cli.main import app
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.infra.models import Base, JobModel, WorkerModel
from libs.services.database import SessionManager


runner = CliRunner()


def _seed_basic(instance_root: Path) -> None:
    database_path = instance_root / "xqueue.db"
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 20, 30, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            WorkerModel(
                id="worker-1",
                state="active",
                queues=["agent"],
                heartbeat_at=now,
                started_at=now,
                process_id=12345,
                concurrency=1,
            )
        )
        session.add_all(
            [
                JobModel(
                    id="job-1",
                    queue="agent",
                    command="echo hi",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="queued",
                ),
                JobModel(
                    id="job-2",
                    queue="agent",
                    command="echo fail",
                    shell=True,
                    priority=20,
                    created_at=now + timedelta(seconds=1),
                    available_at=now + timedelta(seconds=1),
                    state="failed",
                    attempt_count=1,
                ),
            ]
        )
    engine.dispose()


def test_health_tmux_output(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_basic(instance)

        result = runner.invoke(
            app,
            ["health", "--output", "tmux", "--workspace-instance"],
        )

        assert result.exit_code == 0
        output = result.stdout.strip()
        assert "status=" in output
        assert "database_status=" in output


def test_jobs_list_tmux_output(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_basic(instance)

        result = runner.invoke(
            app,
            ["jobs", "list", "--output", "tmux", "--workspace-instance"],
        )

        assert result.exit_code == 0
        output = result.stdout.strip()
        assert "2 items" in output
        assert "job-1" in output
        assert "job-2" in output


def test_jobs_list_tmux_output_with_state_filter(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_basic(instance)

        result = runner.invoke(
            app,
            ["jobs", "list", "--state", "failed", "--output", "tmux", "--workspace-instance"],
        )

        assert result.exit_code == 0
        output = result.stdout.strip()
        assert "1 items" in output
        assert "job-2" in output


def test_controller_status_tmux_output(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_basic(instance)

        result = runner.invoke(
            app,
            ["controller", "status", "--output", "tmux", "--workspace-instance"],
        )

        assert result.exit_code == 0
        output = result.stdout.strip()
        assert "controller_id=" in output
