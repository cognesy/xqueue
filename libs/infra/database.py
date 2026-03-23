"""SQLite engine and session setup for xqueue."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


DEFAULT_BUSY_TIMEOUT_MS = 5_000


def sqlite_url(database_path: Path) -> str:
    """Return a SQLAlchemy SQLite URL for the given path."""
    return f"sqlite+pysqlite:///{database_path}"


def create_sqlite_engine(
    database_path: Path,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> Engine:
    """Create an SQLite engine configured for xqueue's durability requirements."""
    database_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        sqlite_url(database_path),
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory with explicit transaction control."""
    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session without implicit transaction handling."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
