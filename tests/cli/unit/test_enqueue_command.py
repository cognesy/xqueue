from __future__ import annotations

import json
from pathlib import Path

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
