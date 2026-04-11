"""Helpers for launching the xqueue CLI through Python."""

from __future__ import annotations

from pathlib import Path


def xqueue_repo_root() -> Path:
    """Return the repository root that owns the importable xqueue modules."""

    return Path(__file__).resolve().parents[2]


def xqueue_main_bootstrap_code() -> str:
    """Return Python code that imports xqueue's CLI independent of cwd."""

    return (
        "import sys; "
        f"sys.path.insert(0, {str(xqueue_repo_root())!r}); "
        "from apps.cli.main import main; "
        "main()"
    )


def xqueue_python_command(python_executable: str, *args: str) -> list[str]:
    """Return a Python command that invokes xqueue's Typer entrypoint."""

    return [python_executable, "-c", xqueue_main_bootstrap_code(), *args]
