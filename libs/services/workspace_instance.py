"""Repo-local workspace-instance maintenance services."""

from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config

from libs.domain.config import RuntimePaths
from libs.domain.models import WorkspaceInstanceResetResult


class WorkspaceInstanceService:
    """Reset owned repo-local instance artifacts used for manual verification."""

    def reset(self, *, paths: RuntimePaths, alembic_ini_path: Path) -> WorkspaceInstanceResetResult:
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

        config = Config(str(alembic_ini_path))
        repo_root = alembic_ini_path.parent
        config.set_main_option("script_location", str(repo_root / "resources" / "alembic"))
        config.set_main_option("prepend_sys_path", str(repo_root))
        with self._database_path_override(paths.database_path):
            command.upgrade(config, "head")
        recreated_paths.append(str(paths.database_path))

        return WorkspaceInstanceResetResult(
            state_root=str(paths.state_root),
            config_file=str(paths.config_file),
            removed_paths=removed_paths,
            recreated_paths=recreated_paths,
        )

    @contextmanager
    def _database_path_override(self, database_path: Path):
        previous = os.environ.get("XQUEUE_DB_PATH")
        os.environ["XQUEUE_DB_PATH"] = str(database_path)
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("XQUEUE_DB_PATH", None)
            else:
                os.environ["XQUEUE_DB_PATH"] = previous
