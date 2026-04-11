from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text
from typer.testing import CliRunner

from apps.cli.exit_codes import ExitCode
from apps.cli.main import app
from libs.infra.database import create_sqlite_engine
from libs.infra.models import Base


runner = CliRunner()


def test_enqueue_command_returns_json_mutation_response(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
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
                "--output",
                "json",
                "--workspace-instance",
                "--",
                "echo",
                "hello",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)

        assert payload["ok"] is True
        assert payload["item"]["queue"] == "agent"
        assert payload["item"]["command"] == "echo hello"
        assert payload["item"]["state"] == "queued"


def test_enqueue_command_parses_execution_options_and_env(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
        instance.mkdir(exist_ok=True)
        work_dir = Path.cwd() / "work"
        work_dir.mkdir()
        database_path = instance / "xqueue.db"
        engine = create_sqlite_engine(database_path)
        Base.metadata.create_all(engine)
        engine.dispose()

        result = runner.invoke(
            app,
            [
                "enqueue",
                "--queue",
                "agent",
                "--cwd",
                str(work_dir),
                "--timeout-seconds",
                "300",
                "--max-attempts",
                "3",
                "--created-by",
                "tester",
                "--env",
                "AGENT_NAME=writer-1",
                "--output",
                "json",
                "--workspace-instance",
                "--",
                "/bin/sh",
                "-lc",
                "echo hi",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        item = payload["item"]
        assert item["queue"] == "agent"
        assert item["command"] == "/bin/sh -lc 'echo hi'"
        assert item["cwd"] == str(work_dir)
        assert item["timeout_seconds"] == 300
        assert item["max_attempts"] == 3
        assert item["created_by"] == "tester"
        assert item["env"] == {"AGENT_NAME": "writer-1"}

        engine = create_sqlite_engine(database_path)
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT command, cwd, env, timeout_seconds, max_attempts, created_by FROM jobs WHERE id = :job_id"),
                {"job_id": item["id"]},
            ).one()
        engine.dispose()

        assert row.command == "/bin/sh -lc 'echo hi'"
        assert row.cwd == str(work_dir)
        assert json.loads(row.env) == {"AGENT_NAME": "writer-1"}
        assert row.timeout_seconds == 300
        assert row.max_attempts == 3
        assert row.created_by == "tester"


def test_enqueue_command_returns_validation_error_for_missing_command(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
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
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == int(ExitCode.VALIDATION_ERROR)
        payload = json.loads(result.stdout)

        assert payload["ok"] is False
        assert payload["error"]["code"] == "validation_error"
        assert payload["error"]["message"] == "enqueue requires a command after '--'"


def test_enqueue_command_returns_validation_error_for_invalid_env_item(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path("instance")
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
                "--env",
                "BROKEN",
                "--output",
                "json",
                "--workspace-instance",
                "--",
                "echo",
                "hello",
            ],
        )

        assert result.exit_code == int(ExitCode.VALIDATION_ERROR)
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "validation_error"
        assert payload["error"]["message"] == "environment items must use KEY=VALUE format"
        assert payload["error"]["details"] == {"item": "BROKEN"}
