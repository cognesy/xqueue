"""The console-script entrypoint, importable without the `cli` extra.

`xq` is declared by the base distribution, so a bare `pip install xqueue`
installs the script whether or not the CLI frameworks are present. This module
is what the script points at, and it imports nothing outside the standard
library at module scope, so running it without the extra produces one line an
operator can act on instead of a traceback from inside Typer's import graph.

The real entrypoint is `xqueue_cli.main`, imported lazily below.
"""

from __future__ import annotations

import sys

#: Top-level modules that arrive only with the `cli` extra. A `ModuleNotFoundError`
#: naming one of these is a missing install; anything else is a real bug and is
#: re-raised with its traceback intact.
#:
#: `click` is deliberately absent: Typer vendored it in 0.27, so a missing
#: `click` no longer means a missing extra. Listing it turned an accidental
#: `import click` in the CLI into a plausible-looking "install the extra"
#: message instead of the loud failure it was.
CLI_MODULES = frozenset({"rich", "toon", "typer"})

HINT = 'xq requires the cli extra: pip install "xqueue[cli]"'


def main() -> None:
    """Run the CLI, or explain why it cannot run."""
    try:
        from xqueue_cli.main import main as run_cli
    except ModuleNotFoundError as exc:
        root = (exc.name or "").split(".", 1)[0]
        if root not in CLI_MODULES:
            raise
        print(HINT, file=sys.stderr)
        raise SystemExit(2) from None
    run_cli()
