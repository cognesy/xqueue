from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
from typer import Context
from typer.testing import CliRunner

from xqueue_cli.main import app
from xqueue_cli.output import Output, OutputFormat
from xqueue_libs.infra.database import create_session_factory, create_sqlite_engine
from xqueue_libs.infra.models import AttemptModel, Base, JobModel, WorkerModel
from xqueue_libs.services.database import SessionManager


runner = CliRunner()


def _seed_job_for_json_contract(database_path: Path) -> None:
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 23, 40, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            WorkerModel(
                id="worker-json",
                state="active",
                queues=["agent"],
                heartbeat_at=now,
                started_at=now,
            )
        )
        session.add(
            JobModel(
                id="job-json-contract",
                queue="agent",
                command="echo json",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="failed",
                attempt_count=1,
                max_attempts=1,
                last_error="command exited with code 1",
            )
        )
        session.add(
            AttemptModel(
                job_id="job-json-contract",
                attempt_number=1,
                worker_id="worker-json",
                state="failed",
                started_at=now,
                finished_at=now + timedelta(seconds=1),
                exit_code=1,
                error="command exited with code 1",
            )
        )

    engine.dispose()


def test_json_output_bypasses_rich_formatting_even_with_terminal_console() -> None:
    payload = {
        "item": {
            "message": "x" * 240,
            "nested": {"alpha": 1, "beta": [1, 2, 3]},
        }
    }

    out = Output(Context(click.Command("test"), obj={"output": OutputFormat.JSON}), "config.show")

    rendered = out.render(payload)
    assert rendered == json.dumps(payload, indent=2)
    assert "\x1b[" not in rendered


def test_jobs_show_json_uses_utc_timestamps_after_sqlite_round_trip(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        _seed_job_for_json_contract(instance / "xqueue.db")

        result = runner.invoke(
            app,
            [
                "jobs",
                "show",
                "job-json-contract",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert payload["item"]["created_at"].endswith("Z")
        assert payload["item"]["available_at"].endswith("Z")
        assert payload["item"]["attempts"][0]["started_at"].endswith("Z")
        assert payload["item"]["attempts"][0]["finished_at"].endswith("Z")
