"""Context-agnostic database services used by actions."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator, TypeVar

from sqlalchemy.orm import Session, sessionmaker


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
