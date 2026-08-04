"""The typed workspace, and the paths derived from it.

Capability code receives a `Workspace` and never rediscovers a root: passing it
in is what lets two clients on two different workspaces coexist in one process,
which the SDK has always supported and now states explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from xqueue.workspace.marker import WorkspaceMarker
from xqueue.workspace.models import RuntimePaths


class WorkspaceScope(StrEnum):
    """Which of the two instances a workspace refers to."""

    #: The machine-wide instance: `XQUEUE_HOME`, or `~/.xqueue`.
    HOME = "home"
    #: A project instance: `<root>/.xqueue/`.
    PROJECT = "project"


@dataclass(frozen=True)
class Workspace:
    """Where this client's state lives, and how that was decided.

    `root` is the directory a human would name — the project root, or the home
    directory. `directory` is where xqueue keeps its state inside it. For the
    home instance the two differ only by the `.xqueue` component, but keeping
    both means callers never have to know which convention applies.
    """

    root: Path
    directory: Path
    scope: WorkspaceScope
    marker: WorkspaceMarker | None

    @property
    def is_initialized(self) -> bool:
        """Whether a validated marker was found. Absent is not an error."""
        return self.marker is not None


def derive_runtime_paths(workspace: Workspace, *, config_file: Path | None = None) -> RuntimePaths:
    """The five paths every capability uses, all under one directory."""
    directory = workspace.directory
    return RuntimePaths(
        config_file=config_file or directory / "config.yaml",
        state_root=directory,
        runtime_root=directory / "run",
        log_root=directory / "logs",
        database_path=directory / "xqueue.db",
    )
