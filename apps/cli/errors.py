"""One place where an xqueue error becomes a rendered envelope and an exit code.

`run_action` covers failures *inside* an action, but a command opens its client
before it gets there, and configuration composition fails at exactly that
moment. Rather than restructure every command around that one case, the group
itself catches `XqueueError` on the way out, so `--set worker.nonsense=1` and a
missing `--config` file exit the same way a failed `jobs show` does.
"""

from __future__ import annotations

from typing import Any, cast

import typer
from typer.core import TyperGroup
from xqueue.core.errors import XqueueError
from xqueue_cli.exit_codes import map_error_to_exit_code
from xqueue_cli.output import Output


class XqueueGroup(TyperGroup):
    """A Typer group that renders xqueue errors instead of raising them."""

    # `ctx` is a click `Context`, which cannot be named here: Typer vendored
    # click in 0.27, so the importable `click` is not necessarily the one whose
    # Context this is. `Any` keeps the override compatible with both.
    def invoke(self, ctx: Any) -> object:
        try:
            return super().invoke(ctx)
        except XqueueError as exc:
            # `error` is the generic envelope contract; the command's own
            # contract never got as far as being selected.
            Output(cast(typer.Context, ctx), "error").error(
                exc.message,
                code=exc.code,
                details=exc.details,
                exit_code=int(map_error_to_exit_code(exc)),
            )


__all__ = ["XqueueGroup"]
