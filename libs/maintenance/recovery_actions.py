"""Stale-lease recovery action."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from xqueue.adapters.sqlite.session import SessionManager
from xqueue.maintenance.models import RecoverStaleLeasesResult
from xqueue.maintenance.recovery import RecoveryService
from xqueue.runtime.action_logging import log_action


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class RecoverStaleLeasesAction:
    """Recover expired running-job leases."""

    def __init__(
        self,
        session_manager: SessionManager,
        recovery_service: RecoveryService,
        *,
        retry_delay_seconds: int,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._recovery_service = recovery_service
        self._retry_delay_seconds = retry_delay_seconds
        self._clock = clock

    @log_action(
        "recover_stale_leases",
        context_getter=lambda self, retry_delay_seconds=None: {
            "retry_delay_seconds": self._retry_delay_seconds if retry_delay_seconds is None else retry_delay_seconds
        },
        result_getter=lambda result: {"recovered_count": result.recovered_count},
    )
    def __call__(self, retry_delay_seconds: int | None = None) -> RecoverStaleLeasesResult:
        with self._session_manager.transaction() as session:
            item = self._recovery_service.recover_stale_leases(
                session,
                now=self._clock(),
                retry_delay_seconds=(self._retry_delay_seconds if retry_delay_seconds is None else retry_delay_seconds),
            )
        return item
