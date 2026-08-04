"""The installed version of xqueue, resolved without importing the CLI stack.

This module imports only the standard library, so `xqueue_cli.entry` can answer
`--version` before it knows whether Typer is installed. That is the whole point
of the flag: it says which build is on `PATH`, and it must not need the parts of
the install it is being used to check.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

#: The distribution name, which is not the import package name (`xqueue_cli`).
DISTRIBUTION = "xqueue"

#: Reported when the distribution metadata is absent, which happens when the
#: source tree is on `sys.path` without having been installed at all. A string
#: keeps every caller total; nobody has to handle an exception to print a line.
UNKNOWN = "unknown"


def resolve_version() -> str:
    """The installed distribution version, or `UNKNOWN` if it is not installed."""
    try:
        return _distribution_version(DISTRIBUTION)
    except PackageNotFoundError:
        return UNKNOWN


def version_line() -> str:
    """The one line `--version` prints, on stdout, in every output mode."""
    return f"xq {resolve_version()}"


__all__ = ["DISTRIBUTION", "UNKNOWN", "resolve_version", "version_line"]
