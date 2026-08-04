from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner
from xqueue import Xqueue
from xqueue.core.errors import (
    ConflictError,
    NotFoundError,
    OperationTimeoutError,
    RuntimeExecutionError,
    ValidationError,
)
from xqueue_cli.exit_codes import ExitCode, map_error_to_exit_code
from xqueue_cli.main import app

runner = CliRunner()


def test_config_show_supports_json_output() -> None:
    result = runner.invoke(app, ["config", "show", "--output", "json", "--workspace-instance"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload.keys()) == {"paths", "queue", "worker", "controller", "layers"}
    assert payload["paths"]["database_path"].endswith(".xqueue/xqueue.db")


def test_config_show_reports_the_layer_order_it_used() -> None:
    result = runner.invoke(app, ["config", "show", "--output", "json", "--workspace-instance"])

    assert result.exit_code == 0
    layers = json.loads(result.stdout)["layers"]

    assert [layer["layer"] for layer in layers] == [
        "packaged-default",
        "user",
        "workspace",
        "environment",
        "override",
    ]
    assert all("origin" in layer and "applied" in layer for layer in layers)


def test_a_set_override_reaches_the_effective_configuration() -> None:
    result = runner.invoke(
        app,
        ["--set", "worker.retry_delay_seconds=42", "config", "show", "-o", "json", "--workspace-instance"],
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["worker"]["retry_delay_seconds"] == 42


def test_an_unknown_configuration_key_exits_two_with_an_envelope(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("worker:\n  nonsense: 1\n")

    # `-o` must be given at the root: the failure happens while the command is
    # opening its client, so its own output option was never reached.
    result = runner.invoke(app, ["-o", "json", "--config", str(bad), "config", "show"])

    assert result.exit_code == 2, result.stdout
    assert json.loads(result.stdout)["error"]["code"] == "configuration_error"


def test_a_malformed_set_is_rejected_before_anything_opens() -> None:
    result = runner.invoke(app, ["-o", "json", "--set", "nonsense", "config", "show"])

    assert result.exit_code == 2, result.stdout
    assert json.loads(result.stdout)["error"]["code"] == "validation_error"


def test_the_sdk_and_the_cli_compose_the_same_settings(tmp_path: Path) -> None:
    """One loader, two channels. `config show` is a view, not a second resolver."""
    workspace = tmp_path / "project"
    workspace.mkdir()
    (workspace / ".xqueue").mkdir()
    (workspace / ".xqueue" / "config.yaml").write_text("worker:\n  poll_interval_seconds: 3\n")

    result = runner.invoke(
        app,
        [
            "--set",
            "worker.retry_delay_seconds=42",
            "config",
            "show",
            "-o",
            "json",
            "--workspace",
            str(workspace),
        ],
    )
    assert result.exit_code == 0, result.stdout

    with Xqueue.open(
        workspace_root=workspace,
        use_workspace_instance=True,
        overrides={"worker.retry_delay_seconds": "42"},
    ) as client:
        through_the_sdk = client.workspace.config()

    assert json.loads(result.stdout) == json.loads(through_the_sdk.model_dump_json())


def test_config_show_supports_text_output() -> None:
    result = runner.invoke(app, ["config", "show", "--output", "text", "--workspace-instance"])

    assert result.exit_code == 0
    assert "database_path" in result.stdout
    assert ".xqueue/xqueue.db" in result.stdout


def test_exit_code_mapping_covers_shared_error_types() -> None:
    assert map_error_to_exit_code(ValidationError("bad input")) == ExitCode.VALIDATION_ERROR
    assert map_error_to_exit_code(NotFoundError("missing")) == ExitCode.NOT_FOUND
    assert map_error_to_exit_code(ConflictError("conflict")) == ExitCode.CONFLICT
    assert map_error_to_exit_code(OperationTimeoutError("timed out")) == ExitCode.TIMEOUT
    assert map_error_to_exit_code(RuntimeExecutionError("boom")) == ExitCode.RUNTIME_ERROR
