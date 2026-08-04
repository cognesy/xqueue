"""Creating a workspace, idempotently.

`init` is the only thing that writes a marker. It is safe to run twice, it
never overwrites configuration without being told to, and it reports what it
did rather than leaving the caller to diff the directory afterwards.
"""

from __future__ import annotations

from pathlib import Path

from xqueue.workspace.marker import (
    CURRENT_SCHEMA,
    MARKER_NAME,
    build_marker,
    marker_path,
    render_marker,
)
from xqueue.workspace.models import WorkspaceInitResult
from xqueue.workspace.paths import Workspace, derive_runtime_paths

#: Written when a workspace has no config file yet. Deliberately minimal: the
#: defaults live in the models, and a new workspace should not start life with
#: a copy of them to drift from.
STARTER_CONFIG = """\
# xqueue workspace configuration. Every key is optional; unset keys use the
# built-in defaults, which `xq config show` prints in full.
#
# queue:
#   default_queue: default
# worker:
#   poll_interval_seconds: 1.0
#   default_timeout_seconds: 3600
"""


class WorkspaceInitService:
    """Create or complete the `.xqueue/` directory for one workspace."""

    def initialize(
        self,
        workspace: Workspace,
        *,
        created_by: str,
        force: bool = False,
    ) -> WorkspaceInitResult:
        created: list[str] = []
        retained: list[str] = []
        conflicting: list[str] = []
        paths = derive_runtime_paths(workspace)

        if workspace.directory.exists() and not workspace.directory.is_dir():
            # A file where the workspace directory belongs. Nothing below can
            # succeed, and removing it is the operator's decision, not ours.
            return WorkspaceInitResult(
                root=str(workspace.root),
                directory=str(workspace.directory),
                scope=str(workspace.scope),
                conflicting_paths=[str(workspace.directory)],
            )

        for directory in (workspace.directory, paths.runtime_root, paths.log_root):
            if directory.is_dir():
                retained.append(str(directory))
            elif directory.exists():
                conflicting.append(str(directory))
            else:
                directory.mkdir(parents=True)
                created.append(str(directory))

        marker_file = marker_path(workspace.directory)
        if workspace.marker is not None and workspace.marker.schema_version == CURRENT_SCHEMA:
            retained.append(str(marker_file))
        else:
            _write_atomically(marker_file, render_marker(build_marker(created_by)))
            created.append(str(marker_file))

        config_file = paths.config_file
        if config_file.exists() and not force:
            retained.append(str(config_file))
        else:
            _write_atomically(config_file, STARTER_CONFIG)
            created.append(str(config_file))

        return WorkspaceInitResult(
            root=str(workspace.root),
            directory=str(workspace.directory),
            scope=str(workspace.scope),
            created_paths=created,
            retained_paths=retained,
            conflicting_paths=conflicting,
        )


def _write_atomically(path: Path, content: str) -> None:
    """Write through a sibling temporary file, so a crash leaves the old one."""
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


__all__ = ["MARKER_NAME", "STARTER_CONFIG", "WorkspaceInitService"]
