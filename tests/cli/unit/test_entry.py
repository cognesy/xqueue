"""The console-script entrypoint, which must work before Typer is known to exist."""

from __future__ import annotations

import pytest
from xqueue_cli.entry import _is_version_request
from xqueue_cli.version import version_line


def test_version_line_names_the_command_and_a_version() -> None:
    line = version_line()

    assert line.startswith("xq ")
    assert line.split()[1]


@pytest.mark.parametrize("argv", [["--version"]])
def test_bare_version_is_answered_without_typer(argv: list[str]) -> None:
    assert _is_version_request(argv) is True


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--help"],
        ["health"],
        # The one that matters: an operator queueing someone else's version
        # flag. Matching `--version` anywhere would swallow this and print ours
        # instead of enqueueing their job.
        ["enqueue", "--queue", "default", "--", "mytool", "--version"],
        ["enqueue", "--", "sh", "-lc", "mytool --version"],
        # Combined forms still reach Typer, which owns the general case.
        ["--version", "-o", "json"],
        ["-o", "json", "--version"],
    ],
)
def test_everything_else_is_left_to_typer(argv: list[str]) -> None:
    assert _is_version_request(argv) is False
