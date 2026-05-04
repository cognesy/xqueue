"""Recovery-oriented actions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from xqueue_libs.actions.logging import log_action
from xqueue_libs.domain.responses import MutationResponse
from xqueue_libs.services.database import SessionManager
from xqueue_libs.services.recovery import RecoveryService


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
        context_getter=lambda self: {"retry_delay_seconds": self._retry_delay_seconds},
        result_getter=lambda result: {"recovered_count": result.item.recovered_count},
    )
    def __call__(self) -> MutationResponse:
        with self._session_manager.transaction() as session:
            item = self._recovery_service.recover_stale_leases(
                session,
                now=self._clock(),
                retry_delay_seconds=self._retry_delay_seconds,
            )
        return MutationResponse(item=item)
