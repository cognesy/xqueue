"""Presentation shapes for controller pool mutations, owned by the CLI channel."""

from __future__ import annotations

from xqueue.controller.models import ControllerPoolConfigView, ControllerPoolMutationResult
from xqueue_cli.contracts import PayloadConvertible

RESTART_COMMAND = "xq controller restart"


class ControllerPoolMutationView(PayloadConvertible):
    """Pool mutation as the CLI renders it; the shell command text is channel-owned."""

    action: str
    name: str
    pool: ControllerPoolConfigView | None = None
    config_path: str
    restart_required: bool
    restart_command: str | None = None


def for_display(result: ControllerPoolMutationResult) -> ControllerPoolMutationView:
    """Attach the remediation command the operator should run in this channel."""
    return ControllerPoolMutationView(
        **result.model_dump(),
        restart_command=RESTART_COMMAND if result.restart_required else None,
    )
