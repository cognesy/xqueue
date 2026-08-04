"""Queue capability actions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from xqueue.adapters.sqlite.session import SessionManager
from xqueue.queues.models import PurgeJobsResult, QueueStatsView, QueueView
from xqueue.queues.store import QueueService
from xqueue.runtime.action_logging import log_action


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
        result_getter=lambda result: {"item_count": len(result)},
    )
    def __call__(self) -> list[QueueView]:
        with self._session_manager.session() as session:
            items = self._queue_service.list_queues(session)
        return items


class ListQueueStatsAction:
    """Return queue statistics views."""

    def __init__(self, session_manager: SessionManager, queue_service: QueueService) -> None:
        self._session_manager = session_manager
        self._queue_service = queue_service

    @log_action(
        "list_queue_stats",
        result_getter=lambda result: {"item_count": len(result)},
    )
    def __call__(self) -> list[QueueStatsView]:
        with self._session_manager.session() as session:
            items = self._queue_service.list_queue_stats(session)
        return items


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
            "queue": result.name,
            "queue_state": result.state.value,
        },
    )
    def __call__(self, queue: str) -> QueueView:
        with self._session_manager.transaction() as session:
            item = self._queue_service.pause_queue(session, queue=queue, now=self._clock())
        return item


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
            "queue": result.name,
            "queue_state": result.state.value,
        },
    )
    def __call__(self, queue: str) -> QueueView:
        with self._session_manager.transaction() as session:
            item = self._queue_service.resume_queue(session, queue=queue, now=self._clock())
        return item


class PurgeJobsAction:
    """Delete queued or retry-scheduled jobs for one queue."""

    def __init__(self, session_manager: SessionManager, queue_service: QueueService) -> None:
        self._session_manager = session_manager
        self._queue_service = queue_service

    @log_action(
        "purge_jobs",
        context_getter=lambda self, queue: {"queue": queue},
        result_getter=lambda result: {
            "queue": result.queue,
            "deleted_count": result.deleted_count,
        },
    )
    def __call__(self, queue: str) -> PurgeJobsResult:
        with self._session_manager.transaction() as session:
            return self._queue_service.purge_jobs(session, queue=queue)
