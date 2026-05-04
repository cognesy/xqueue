from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from xqueue_cli.main import app
from xqueue_libs.infra.database import create_session_factory, create_sqlite_engine
from xqueue_libs.infra.models import Base, JobModel
from xqueue_libs.services.database import SessionManager


runner = CliRunner()


def _seed_queue_jobs(database_path: Path) -> None:
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 22, 0, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add_all(
            [
                JobModel(
                    id="job-alpha-queued",
                    queue="alpha",
                    command="echo alpha",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="queued",
                ),
                JobModel(
                    id="job-alpha-running",
                    queue="alpha",
                    command="echo alpha running",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="running",
                ),
                JobModel(
                    id="job-beta-failed",
                    queue="beta",
                    command="echo beta",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="failed",
                ),
            ]
        )

    engine.dispose()


def test_queues_list_and_stats_return_json(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_queue_jobs(instance / "xqueue.db")

        list_result = runner.invoke(app, ["queues", "list", "--output", "json", "--workspace-instance"])
        stats_result = runner.invoke(app, ["queues", "stats", "--output", "json", "--workspace-instance"])

        assert list_result.exit_code == 0
        assert stats_result.exit_code == 0

        list_payload = json.loads(list_result.stdout)
        stats_payload = json.loads(stats_result.stdout)

        assert [item["name"] for item in list_payload["items"]] == ["alpha", "beta"]
        alpha_stats = next(item for item in stats_payload["items"] if item["name"] == "alpha")
        assert alpha_stats["queued_jobs"] == 1
        assert alpha_stats["running_jobs"] == 1


def test_queues_pause_and_resume_return_mutation_json(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_queue_jobs(instance / "xqueue.db")

        pause_result = runner.invoke(
            app,
            ["queues", "pause", "alpha", "--output", "json", "--workspace-instance"],
        )
        resume_result = runner.invoke(
            app,
            ["queues", "resume", "alpha", "--output", "json", "--workspace-instance"],
        )

        assert pause_result.exit_code == 0
        assert resume_result.exit_code == 0

        pause_payload = json.loads(pause_result.stdout)
        resume_payload = json.loads(resume_result.stdout)

        assert pause_payload["item"]["state"] == "paused"
        assert pause_payload["item"]["paused_at"] is not None
        assert resume_payload["item"]["state"] == "active"
        assert resume_payload["item"]["paused_at"] is None
