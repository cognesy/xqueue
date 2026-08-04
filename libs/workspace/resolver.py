"""Deciding which workspace a client operates on.

The order is fixed and total:

1. an explicit root, from an argument or `--workspace`
2. `XQUEUE_ROOT`
3. the nearest parent of a given start directory holding a valid marker
4. the home instance

Step 4 is why there is no `WorkspaceNotFoundError`: xqueue is a machine-wide
queue whose controller supervises pools for many projects, so "no workspace
here" is a normal answer, not a failure. What is always a failure is a marker
that exists and does not check out -- see `xqueue.workspace.marker`.

Step 3 never creates anything: discovery must not guess. Steps 1 and 2 name a
directory outright, so an uninitialized one is simply not initialized yet, and
`workspace init` -- or the first client to open it -- fills it in.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from xqueue.workspace.marker import WORKSPACE_DIR, read_marker
from xqueue.workspace.paths import Workspace, WorkspaceScope

#: Names a workspace root, the way `XQUEUE_HOME` names the home instance.
ROOT_ENV_VAR = "XQUEUE_ROOT"

#: Overrides the location of the machine-wide instance.
HOME_ENV_VAR = "XQUEUE_HOME"


def resolve_workspace(
    *,
    explicit_root: Path | None = None,
    start_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Workspace:
    """Apply the four steps and return the workspace that won."""
    env = os.environ if environ is None else environ

    if explicit_root is not None:
        return project_workspace(explicit_root)

    configured_root = env.get(ROOT_ENV_VAR)
    if configured_root:
        return project_workspace(Path(configured_root).expanduser())

    if start_dir is not None:
        discovered = discover_workspace(start_dir)
        if discovered is not None:
            return discovered

    return home_workspace(environ=env)


def project_workspace(root: Path) -> Workspace:
    """The workspace at a named root, initialized or not."""
    resolved = root.expanduser().resolve()
    directory = resolved / WORKSPACE_DIR
    return Workspace(
        root=resolved,
        directory=directory,
        scope=WorkspaceScope.PROJECT,
        marker=read_marker(directory),
    )


def discover_workspace(start_dir: Path) -> Workspace | None:
    """The nearest ancestor of `start_dir` that is a workspace, if any.

    A malformed marker anywhere on the way up raises rather than being skipped:
    the whole purpose of walking is to stop at the first workspace, so a broken
    one is the answer, not an obstacle to step over.
    """
    current = start_dir.expanduser().resolve()
    for directory in (current, *current.parents):
        marker = read_marker(directory / WORKSPACE_DIR)
        if marker is not None:
            return Workspace(
                root=directory,
                directory=directory / WORKSPACE_DIR,
                scope=WorkspaceScope.PROJECT,
                marker=marker,
            )
    return None


def home_workspace(*, environ: Mapping[str, str] | None = None) -> Workspace:
    """The machine-wide instance: `XQUEUE_HOME`, or `~/.xqueue`."""
    env = os.environ if environ is None else environ
    configured = env.get(HOME_ENV_VAR)
    directory = Path(configured).expanduser() if configured else Path.home() / WORKSPACE_DIR
    return Workspace(
        root=directory.parent,
        directory=directory,
        scope=WorkspaceScope.HOME,
        marker=read_marker(directory),
    )
