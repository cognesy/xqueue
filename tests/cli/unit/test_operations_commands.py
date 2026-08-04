from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner
from xqueue.adapters.sqlite.database import create_session_factory, create_sqlite_engine
from xqueue.adapters.sqlite.models import AttemptModel, Base, JobModel, QueueModel, WorkerModel
from xqueue.adapters.sqlite.session import SessionManager
from xqueue_cli.main import app

runner = CliRunner()


def _seed_operations_state(database_path: Path) -> None:
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime.now(UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(QueueModel(name="alpha", state="paused", updated_at=now, paused_at=now))
        session.add(
            WorkerModel(
                id="worker-cli-stale",
                state="active",
                queues=["alpha"],
                heartbeat_at=now - timedelta(minutes=5),
                started_at=now - timedelta(minutes=10),
            )
        )
        session.add(
            JobModel(
                id="job-cli-stale",
                queue="alpha",
                command="sleep 60",
                shell=True,
                priority=10,
                created_at=now - timedelta(minutes=1),
                available_at=now - timedelta(minutes=1),
                state="running",
                lease_expires_at=now - timedelta(seconds=10),
                worker_id="worker-cli-stale",
                attempt_count=1,
                max_attempts=2,
            )
        )
        session.add(
            AttemptModel(
                job_id="job-cli-stale",
                attempt_number=1,
                worker_id="worker-cli-stale",
                state="running",
                started_at=now - timedelta(minutes=1),
            )
        )

    engine.dispose()


def test_health_and_doctor_return_json(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        _seed_operations_state(instance / "xqueue.db")

        health_result = runner.invoke(app, ["health", "--output", "json", "--workspace-instance"])
        doctor_result = runner.invoke(app, ["doctor", "--output", "json", "--workspace-instance"])

        assert health_result.exit_code == 0
        assert doctor_result.exit_code == 0

        health_payload = json.loads(health_result.stdout)
        doctor_payload = json.loads(doctor_result.stdout)

        assert health_payload["item"]["status"] == "warn"
        assert health_payload["item"]["paused_queues"] == ["alpha"]
        assert health_payload["item"]["stale_leases"][0]["job_id"] == "job-cli-stale"
        assert doctor_payload["item"]["status"] == "warn"
        assert {item["name"] for item in doctor_payload["item"]["checks"]} == {
            "database.integrity",
            "queues.paused",
            "leases.stale",
            "workers.heartbeat",
        }


def test_recover_stale_leases_returns_mutation_json(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        _seed_operations_state(instance / "xqueue.db")

        result = runner.invoke(
            app,
            ["recover", "stale-leases", "--output", "json", "--workspace-instance"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert payload["ok"] is True
        assert payload["item"]["recovered_count"] == 1
        assert payload["item"]["items"][0]["job_id"] == "job-cli-stale"
        assert payload["item"]["items"][0]["new_state"] == "retry_scheduled"


def test_db_check_and_vacuum_return_json(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        _seed_operations_state(instance / "xqueue.db")

        check_result = runner.invoke(app, ["db", "check", "--output", "json", "--workspace-instance"])
        vacuum_result = runner.invoke(app, ["db", "vacuum", "--output", "json", "--workspace-instance"])

        assert check_result.exit_code == 0
        assert vacuum_result.exit_code == 0

        check_payload = json.loads(check_result.stdout)
        vacuum_payload = json.loads(vacuum_result.stdout)

        assert check_payload["item"]["status"] == "ok"
        assert check_payload["item"]["missing_tables"] == []
        assert vacuum_payload["ok"] is True
        assert vacuum_payload["item"]["database_path"].endswith("xqueue.db")
