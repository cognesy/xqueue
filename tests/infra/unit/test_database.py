from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from xqueue_libs.infra.database import create_session_factory, create_sqlite_engine
from xqueue_libs.services.database import SessionManager


def test_sqlite_engine_applies_wal_and_busy_timeout(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "xqueue.db", busy_timeout_ms=7_000)

    with engine.connect() as connection:
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
        busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()

    assert str(journal_mode).lower() == "wal"
    assert busy_timeout == 7_000
    assert foreign_keys == 1


def test_transaction_scope_commits_work(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "xqueue.db")
    session_factory = create_session_factory(engine)
    manager = SessionManager(session_factory)

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"))

    manager.run_in_transaction(
        lambda session: session.execute(
            text("INSERT INTO sample (value) VALUES (:value)"),
            {"value": "committed"},
        )
    )

    with engine.connect() as connection:
        stored = connection.execute(text("SELECT value FROM sample")).scalar_one()

    assert stored == "committed"


def test_transaction_scope_rolls_back_on_error(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "xqueue.db")
    session_factory = create_session_factory(engine)
    manager = SessionManager(session_factory)

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"))

    def failing_insert(session) -> None:
        session.execute(text("INSERT INTO sample (value) VALUES ('rolled-back')"))
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        manager.run_in_transaction(failing_insert)

    with engine.connect() as connection:
        row_count = connection.execute(text("SELECT COUNT(*) FROM sample")).scalar_one()

    assert row_count == 0
