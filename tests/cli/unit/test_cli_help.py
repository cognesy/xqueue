from __future__ import annotations

from typer.testing import CliRunner
from xqueue_cli.main import app

runner = CliRunner()

TOP_LEVEL_COMMANDS = {
    "config",
    "controller",
    "db",
    "doctor",
    "enqueue",
    "health",
    "hooks",
    "jobs",
    "metrics",
    "queues",
    "recover",
    "worker",
    "workers",
}

GROUP_COMMANDS = {
    "controller": {
        "drain",
        "install",
        "pause-intake",
        "pools",
        "restart",
        "resume-intake",
        "run",
        "start",
        "status",
        "stop",
        "uninstall",
    },
    "db": {"check", "cleanup-retention", "reset-workspace-instance", "vacuum"},
    "hooks": {"install", "status"},
    "jobs": {"cancel", "delete", "list", "pane", "prune", "purge", "retry", "show", "tail"},
    "queues": {"list", "pause", "resume", "stats"},
    "workers": {"drain", "list", "pause", "resume", "stop"},
}


def test_top_level_help_renders() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "durable work queue" in result.stdout.lower()
    for command in TOP_LEVEL_COMMANDS:
        assert command in result.stdout


def test_command_group_inventory_is_stable() -> None:
    for group, commands in GROUP_COMMANDS.items():
        result = runner.invoke(app, [group, "--help"])

        assert result.exit_code == 0
        for command in commands:
            assert command in result.stdout


def test_version_prints_the_installed_version_and_exits_clean() -> None:
    """The cheapest possible install check: which build is on PATH."""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0, result.stdout
    assert result.stdout.startswith("xq ")
    assert result.stdout.split()[1]


def test_version_is_listed_in_help() -> None:
    """A flag nobody can discover is a flag nobody uses."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--version" in result.stdout
