from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from xqueue_cli.main import app
from xqueue_libs.infra.database import create_session_factory, create_sqlite_engine
from xqueue_libs.infra.models import Base, WorkerModel
from xqueue_libs.services.database import SessionManager


runner = CliRunner()


def _seed_worker(database_path: Path) -> None:
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 22, 20, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            WorkerModel(
                id="worker-cli",
                state="active",
                queues=["agent"],
                heartbeat_at=now,
                started_at=now,
                hostname="test-host",
                process_id=1234,
                concurrency=2,
            )
        )

    engine.dispose()


def test_workers_list_returns_json(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_worker(instance / "xqueue.db")

        result = runner.invoke(app, ["workers", "list", "--output", "json", "--workspace-instance"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert len(payload["items"]) == 1
        assert payload["items"][0]["id"] == "worker-cli"
        assert payload["items"][0]["state"] == "active"
        assert payload["items"][0]["queues"] == ["agent"]


def test_workers_pause_resume_drain_stop_return_mutation_json(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_worker(instance / "xqueue.db")

        pause_result = runner.invoke(app, ["workers", "pause", "worker-cli", "--output", "json", "--workspace-instance"])
        resume_result = runner.invoke(app, ["workers", "resume", "worker-cli", "--output", "json", "--workspace-instance"])
        drain_result = runner.invoke(app, ["workers", "drain", "worker-cli", "--output", "json", "--workspace-instance"])
        stop_result = runner.invoke(app, ["workers", "stop", "worker-cli", "--output", "json", "--workspace-instance"])

        assert pause_result.exit_code == 0
        assert resume_result.exit_code == 0
        assert drain_result.exit_code == 0
        assert stop_result.exit_code == 0

        assert json.loads(pause_result.stdout)["item"]["state"] == "paused"
        assert json.loads(resume_result.stdout)["item"]["state"] == "active"
        assert json.loads(drain_result.stdout)["item"]["state"] == "draining"
        assert json.loads(stop_result.stdout)["item"]["state"] == "stopped"
