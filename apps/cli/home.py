"""Helpers for the content-first bare xq home view."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from pydantic import ConfigDict, Field
from xqueue.maintenance.models import HomeJobCount, HomeQueueRow, HomeWorkerRow
from xqueue_cli.client import open_client
from xqueue_cli.contracts import PayloadConvertible

DESCRIPTION = "CLI-first durable work queue for shell commands in the current workspace"
HELP_ITEMS = (
    "Run `xq jobs show <job_id>` for full job details",
    "Run `xq enqueue --queue <queue> -- <command>` to add work",
    "Run `xq workers list` to inspect worker state",
)
STATE_STORE_HELP = "Run `xq db check` to inspect the current state store"


class HomeResponse(PayloadConvertible):
    """Presentation shape for the bare xq view; owned by the CLI channel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bin: str
    description: str
    queues: list[HomeQueueRow] = Field(default_factory=list)
    jobs: list[HomeJobCount] = Field(default_factory=list)
    workers: list[HomeWorkerRow] = Field(default_factory=list)
    help: list[str] = Field(default_factory=list)


def collapse_home_path(path: str) -> str:
    """Collapse the user home directory for human-readable paths."""
    home = str(Path.home())
    return path.replace(home, "~", 1) if path.startswith(home) else path


def resolve_executable() -> str:
    """Resolve the absolute xq executable path."""
    which = shutil.which("xq")
    if which:
        return collapse_home_path(str(Path(which).resolve()))
    return collapse_home_path(str(Path(sys.argv[0]).resolve()))


def build_home_response(workspace_root: Path) -> HomeResponse:
    """Build the compact content-first home response for the current workspace."""
    # No probing for a database file here any more: the resolver discovers a
    # project workspace from this directory upward and falls back to the home
    # instance, which is the same decision every other command makes.
    with open_client(workspace_root=workspace_root) as xq:
        snapshot = xq.maintenance.home()

    help_items = list(HELP_ITEMS)
    if not snapshot.state_store_available:
        help_items.append(STATE_STORE_HELP)

    return HomeResponse(
        bin=resolve_executable(),
        description=DESCRIPTION,
        queues=snapshot.queues,
        jobs=snapshot.jobs,
        workers=snapshot.workers,
        help=help_items,
    )
