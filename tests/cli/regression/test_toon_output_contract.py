from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner
from xqueue.adapters.sqlite.database import create_session_factory, create_sqlite_engine
from xqueue.adapters.sqlite.models import Base, JobModel
from xqueue.adapters.sqlite.session import SessionManager
from xqueue_cli.main import app

runner = CliRunner()


def _seed_job(database_path: Path) -> None:
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 4, 10, 20, 0, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-toon",
                queue="agent",
                command="echo toon",
                shell=True,
                priority=100,
                created_at=now,
                available_at=now,
                state="queued",
                attempt_count=0,
                max_attempts=1,
            )
        )

    engine.dispose()


def test_jobs_list_default_toon_contract_is_stable(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        _seed_job(instance / "xqueue.db")

        result = runner.invoke(app, ["jobs", "list", "--workspace-instance"])

        assert result.exit_code == 0
        assert "items[1,]{id,queue,state,available_at}:" in result.stdout
        assert "job-toon,agent,queued" in result.stdout


def test_global_output_json_propagates_to_jobs_list(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        _seed_job(instance / "xqueue.db")

        result = runner.invoke(app, ["-o", "json", "jobs", "list", "--workspace-instance"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["items"][0]["id"] == "job-toon"
        assert payload["items"][0]["queue"] == "agent"
        assert payload["meta"] is None


def test_global_output_jsonl_propagates_to_jobs_list(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        _seed_job(instance / "xqueue.db")

        result = runner.invoke(app, ["-o", "jsonl", "jobs", "list", "--workspace-instance"])

        assert result.exit_code == 0
        lines = result.stdout.splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["id"] == "job-toon"
        assert payload["queue"] == "agent"


def test_global_fields_option_filters_jobs_list_toon_output(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        _seed_job(instance / "xqueue.db")

        result = runner.invoke(app, ["--fields", "id,state", "jobs", "list", "--workspace-instance"])

        assert result.exit_code == 0
        assert "items[1,]{id,state}:" in result.stdout
        assert "job-toon,queued" in result.stdout
        assert "agent" not in result.stdout


def test_jobs_show_default_toon_detail_contract_is_stable(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        _seed_job(instance / "xqueue.db")

        result = runner.invoke(app, ["jobs", "show", "job-toon", "--workspace-instance"])

        assert result.exit_code == 0
        assert "item:" in result.stdout
        assert "id: job-toon" in result.stdout
        assert "queue: agent" in result.stdout
        assert "state: queued" in result.stdout
        assert "command: echo toon" in result.stdout


def test_enqueue_default_toon_mutation_contract_is_stable(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        engine = create_sqlite_engine(instance / "xqueue.db")
        Base.metadata.create_all(engine)
        engine.dispose()

        result = runner.invoke(
            app,
            [
                "enqueue",
                "--queue",
                "agent",
                "--workspace-instance",
                "--",
                "echo",
                "toon",
            ],
        )

        assert result.exit_code == 0
        assert "ok: true" in result.stdout
        assert "item:" in result.stdout
        assert "queue: agent" in result.stdout
        assert "state: queued" in result.stdout


def test_jobs_show_default_toon_error_contract_is_stable(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        _seed_job(instance / "xqueue.db")

        result = runner.invoke(app, ["jobs", "show", "missing-job", "--workspace-instance"])

        assert result.exit_code != 0
        assert "ok: false" in result.stdout
        assert "error:" in result.stdout
        assert "code: not_found" in result.stdout
        assert "message: job not found" in result.stdout
        assert "job_id: missing-job" in result.stdout
