from __future__ import annotations

from typer.testing import CliRunner

from xqueue_cli.main import app


runner = CliRunner()


def test_top_level_help_renders() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "durable work queue" in result.stdout.lower()
