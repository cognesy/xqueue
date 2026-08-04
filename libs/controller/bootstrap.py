"""Controller helper for launching the installed xqueue CLI."""

from __future__ import annotations


def xqueue_python_command(python_executable: str, *args: str) -> list[str]:
    """Return a Python command that invokes xqueue's installed CLI package."""

    return [python_executable, "-m", "xqueue_cli", *args]
