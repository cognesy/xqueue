"""Explicit SQLite session and transaction boundaries."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator, TypeVar

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from xqueue.core.errors import StateStoreUnavailableError

T = TypeVar("T")


class SessionManager:
    """Provide explicit session and transaction boundaries."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Yield a plain session for explicit read or write orchestration."""
        session = self._session_factory()
        try:
            yield session
        except OperationalError as exc:
            # A missing file or missing schema is an expected operator state, not a
            # bug; give callers one typed error instead of a SQLAlchemy exception.
            raise StateStoreUnavailableError(str(exc.orig or exc), details={"kind": "sqlite"}) from exc
        finally:
            session.close()

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Yield a session inside an explicit transaction boundary."""
        with self.session() as session:
            with session.begin():
                yield session

    def run_in_transaction(self, fn: Callable[[Session], T]) -> T:
        """Execute a callable inside a managed transaction."""
        with self.transaction() as session:
            return fn(session)
