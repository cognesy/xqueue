"""Bringing a workspace database to head, and resetting instance artifacts.

Both things live here because both are the same conversation with Alembic, and
because that conversation is mediated by `XQUEUE_DB_PATH`: the migration
environment reads the database location from the environment, so whoever calls
it has to set that variable for the duration.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from xqueue.runtime.resources import resource_path
from xqueue.workspace.models import RuntimePaths, WorkspaceInstanceResetResult


@contextmanager
def _database_path_override(database_path: Path) -> Iterator[None]:
    """Point the migration environment at one database, then put it back."""
    previous = os.environ.get("XQUEUE_DB_PATH")
    os.environ["XQUEUE_DB_PATH"] = str(database_path)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("XQUEUE_DB_PATH", None)
        else:
            os.environ["XQUEUE_DB_PATH"] = previous


def upgrade_database(database_path: Path) -> None:
    """Run migrations up to head against `database_path`, creating it if absent.

    Idempotent: at head this is a no-op, so callers may run it whenever they
    want the schema to exist rather than having to know whether it does.
    """
    config = Config()
    with resource_path("alembic") as alembic_path:
        config.set_main_option("script_location", str(alembic_path))
        with _database_path_override(database_path):
            command.upgrade(config, "head")


class WorkspaceInstanceService:
    """Reset owned repo-local instance artifacts used for manual verification."""

    def reset(self, *, paths: RuntimePaths) -> WorkspaceInstanceResetResult:
        removed_paths: list[str] = []
        recreated_paths: list[str] = []

        for path in [paths.database_path, paths.runtime_root, paths.log_root]:
            if not path.exists():
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed_paths.append(str(path))

        paths.state_root.mkdir(parents=True, exist_ok=True)
        recreated_paths.append(str(paths.state_root))

        for path in [paths.runtime_root, paths.log_root]:
            path.mkdir(parents=True, exist_ok=True)
            recreated_paths.append(str(path))

        upgrade_database(paths.database_path)
        recreated_paths.append(str(paths.database_path))

        return WorkspaceInstanceResetResult(
            state_root=str(paths.state_root),
            config_file=str(paths.config_file),
            removed_paths=removed_paths,
            recreated_paths=recreated_paths,
        )


__all__ = ["WorkspaceInstanceService", "upgrade_database"]
