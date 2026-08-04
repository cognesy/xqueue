from __future__ import annotations

import os
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from xqueue.adapters.sqlite.database import sqlite_url
from xqueue.adapters.sqlite.models import Base
from xqueue.workspace.loader import SettingsLoader
from xqueue.workspace.resolver import project_workspace

target_metadata = Base.metadata


def get_database_url() -> str:
    explicit_path = os.environ.get("XQUEUE_DB_PATH")
    if explicit_path:
        return sqlite_url(Path(explicit_path))

    workspace_root = Path(os.environ.get("XQUEUE_WORKSPACE_ROOT", Path.cwd()))
    config = SettingsLoader().load(project_workspace(workspace_root))
    return sqlite_url(config.paths.database_path)


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = context.config.get_section(context.config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
