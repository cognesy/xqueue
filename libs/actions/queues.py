"""Queue-related actions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from xqueue_libs.actions.logging import log_action
from xqueue_libs.domain.responses import ListResponse, MutationResponse
from xqueue_libs.services.database import SessionManager
from xqueue_libs.services.queues import QueueService


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class ListQueuesAction:
    """Return queue state views."""

    def __init__(self, session_manager: SessionManager, queue_service: QueueService) -> None:
        self._session_manager = session_manager
        self._queue_service = queue_service

    @log_action(
        "list_queues",
        result_getter=lambda result: {"item_count": len(result.items)},
    )
    def __call__(self) -> ListResponse:
        with self._session_manager.session() as session:
            items = self._queue_service.list_queues(session)
        return ListResponse(items=items)


class ListQueueStatsAction:
    """Return queue statistics views."""

    def __init__(self, session_manager: SessionManager, queue_service: QueueService) -> None:
        self._session_manager = session_manager
        self._queue_service = queue_service

    @log_action(
        "list_queue_stats",
        result_getter=lambda result: {"item_count": len(result.items)},
    )
    def __call__(self) -> ListResponse:
        with self._session_manager.session() as session:
            items = self._queue_service.list_queue_stats(session)
        return ListResponse(items=items)


class PauseQueueAction:
    """Persist paused state for one queue."""

    def __init__(
        self,
        session_manager: SessionManager,
        queue_service: QueueService,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._queue_service = queue_service
        self._clock = clock

    @log_action(
        "pause_queue",
        context_getter=lambda self, queue: {"queue": queue},
        result_getter=lambda result: {
            "queue": result.item.name,
            "queue_state": result.item.state.value,
        },
    )
    def __call__(self, queue: str) -> MutationResponse:
        with self._session_manager.transaction() as session:
            item = self._queue_service.pause_queue(session, queue=queue, now=self._clock())
        return MutationResponse(item=item)


class ResumeQueueAction:
    """Persist active state for one queue."""

    def __init__(
        self,
        session_manager: SessionManager,
        queue_service: QueueService,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._queue_service = queue_service
        self._clock = clock

    @log_action(
        "resume_queue",
        context_getter=lambda self, queue: {"queue": queue},
        result_getter=lambda result: {
            "queue": result.item.name,
            "queue_state": result.item.state.value,
        },
    )
    def __call__(self, queue: str) -> MutationResponse:
        with self._session_manager.transaction() as session:
            item = self._queue_service.resume_queue(session, queue=queue, now=self._clock())
        return MutationResponse(item=item)
