from __future__ import annotations

import json

from typer.testing import CliRunner

from apps.cli.exit_codes import ExitCode, map_error_to_exit_code
from apps.cli.main import app
from libs.domain.errors import ConflictError, NotFoundError, OperationTimeoutError, RuntimeExecutionError, ValidationError


runner = CliRunner()


def test_config_show_supports_json_output() -> None:
    result = runner.invoke(app, ["config", "show", "--output", "json", "--workspace-instance"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload.keys()) == {"paths", "queue", "worker", "controller"}
    assert payload["paths"]["database_path"].endswith("instance/xqueue.db")


def test_config_show_supports_text_output() -> None:
    result = runner.invoke(app, ["config", "show", "--output", "text", "--workspace-instance"])

    assert result.exit_code == 0
    assert "database_path" in result.stdout
    assert "instance/xqueue.db" in result.stdout


def test_exit_code_mapping_covers_shared_error_types() -> None:
    assert map_error_to_exit_code(ValidationError("bad input")) == ExitCode.VALIDATION_ERROR
    assert map_error_to_exit_code(NotFoundError("missing")) == ExitCode.NOT_FOUND
    assert map_error_to_exit_code(ConflictError("conflict")) == ExitCode.CONFLICT
    assert map_error_to_exit_code(OperationTimeoutError("timed out")) == ExitCode.TIMEOUT
    assert map_error_to_exit_code(RuntimeExecutionError("boom")) == ExitCode.RUNTIME_ERROR
