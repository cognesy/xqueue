"""Job-related actions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from libs.actions.logging import log_action
from libs.domain.models import AttemptLogStream, EnqueueJobInput, JobListFilters
from libs.domain.responses import DetailResponse, ListResponse, MutationResponse
from libs.services.database import SessionManager
from libs.services.job_logs import JobLogService
from libs.services.jobs import JobService
from libs.services.pruning import JobPruningService
from libs.services.queues import QueueService


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class EnqueueJobAction:
    """Persist a new queued job."""

    def __init__(
        self,
        session_manager: SessionManager,
        job_service: JobService,
        *,
        clock: Callable[[], datetime] = utc_now,
        id_factory: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        self._session_manager = session_manager
        self._job_service = job_service
        self._clock = clock
        self._id_factory = id_factory

    @log_action(
        "enqueue_job",
        context_getter=lambda self, payload: {
            "queue": payload.queue,
            "priority": payload.priority,
            "max_attempts": payload.max_attempts,
            "has_timeout": payload.timeout_seconds is not None,
        },
        result_getter=lambda result: {
            "job_id": result.item.id,
            "job_state": result.item.state.value,
        },
    )
    def __call__(self, payload: EnqueueJobInput) -> MutationResponse:
        with self._session_manager.transaction() as session:
            item = self._job_service.enqueue(
                session,
                job_id=self._id_factory(),
                payload=payload,
                now=self._clock(),
            )
        return MutationResponse(item=item)


class ListJobsAction:
    """Return operator-visible job summaries."""

    def __init__(self, session_manager: SessionManager, job_service: JobService) -> None:
        self._session_manager = session_manager
        self._job_service = job_service

    @log_action(
        "list_jobs",
        context_getter=lambda self, filters: {
            "queue": filters.queue,
            "state": None if filters.state is None else filters.state.value,
            "worker_id": filters.worker_id,
            "created_after": None if filters.created_after is None else filters.created_after.isoformat(),
            "created_before": None if filters.created_before is None else filters.created_before.isoformat(),
            "available_after": None if filters.available_after is None else filters.available_after.isoformat(),
            "available_before": None if filters.available_before is None else filters.available_before.isoformat(),
            "sort": filters.sort.value,
            "limit": filters.limit,
        },
        result_getter=lambda result: {
            "item_count": len(result.items),
        },
    )
    def __call__(self, filters: JobListFilters) -> ListResponse:
        with self._session_manager.session() as session:
            items = self._job_service.list_jobs(session, filters=filters)
        return ListResponse(items=items)


class ShowJobAction:
    """Return a detailed view of a single job."""

    def __init__(self, session_manager: SessionManager, job_service: JobService) -> None:
        self._session_manager = session_manager
        self._job_service = job_service

    @log_action(
        "show_job",
        context_getter=lambda self, job_id: {"job_id": job_id},
        result_getter=lambda result: {
            "job_id": result.item.id,
            "job_state": result.item.state.value,
        },
    )
    def __call__(self, job_id: str) -> DetailResponse:
        with self._session_manager.session() as session:
            item = self._job_service.get_job(session, job_id=job_id)
        return DetailResponse(item=item)


class CancelJobAction:
    """Cancel a queued job or request cancellation for a running job."""

    def __init__(
        self,
        session_manager: SessionManager,
        job_service: JobService,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._job_service = job_service
        self._clock = clock

    @log_action(
        "cancel_job",
        context_getter=lambda self, job_id: {"job_id": job_id},
        result_getter=lambda result: {
            "job_id": result.item.id,
            "job_state": result.item.state.value,
            "cancel_requested": result.item.cancel_requested_at is not None,
        },
    )
    def __call__(self, job_id: str) -> MutationResponse:
        with self._session_manager.transaction() as session:
            item = self._job_service.cancel_job(session, job_id=job_id, now=self._clock())
        return MutationResponse(item=item)


class RetryJobAction:
    """Requeue a terminal job without deleting attempt history."""

    def __init__(
        self,
        session_manager: SessionManager,
        job_service: JobService,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._job_service = job_service
        self._clock = clock

    @log_action(
        "retry_job",
        context_getter=lambda self, job_id: {"job_id": job_id},
        result_getter=lambda result: {
            "job_id": result.item.id,
            "job_state": result.item.state.value,
            "attempt_count": result.item.attempt_count,
        },
    )
    def __call__(self, job_id: str) -> MutationResponse:
        with self._session_manager.transaction() as session:
            item = self._job_service.retry_job(session, job_id=job_id, now=self._clock())
        return MutationResponse(item=item)


class DeleteJobAction:
    """Delete a non-running job and its associated history."""

    def __init__(
        self,
        session_manager: SessionManager,
        job_service: JobService,
        job_log_service: JobLogService | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._job_service = job_service
        self._job_log_service = job_log_service or JobLogService()

    @log_action(
        "delete_job",
        context_getter=lambda self, job_id: {"job_id": job_id},
        result_getter=lambda result: {
            "job_id": result.item.job_id,
            "deleted_state": result.item.deleted_state.value,
            "deleted_attempt_count": result.item.deleted_attempt_count,
        },
    )
    def __call__(self, job_id: str) -> MutationResponse:
        with self._session_manager.transaction() as session:
            item = self._job_service.delete_job(session, job_id=job_id)

        deleted_log_paths = self._job_log_service.delete_paths(paths=item.deleted_log_paths)
        return MutationResponse(item=item.model_copy(update={"deleted_log_paths": deleted_log_paths}))


class TailJobLogsAction:
    """Return a structured tail view for one attempt log stream."""

    def __init__(
        self,
        session_manager: SessionManager,
        job_service: JobService,
        job_log_service: JobLogService | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._job_service = job_service
        self._job_log_service = job_log_service or JobLogService()

    @log_action(
        "tail_job_logs",
        context_getter=lambda self, job_id, stream, lines, attempt_number=None: {
            "job_id": job_id,
            "stream": stream.value,
            "lines": lines,
            "attempt_number": attempt_number,
        },
        result_getter=lambda result: {
            "job_id": result.item.job_id,
            "attempt_number": result.item.attempt_number,
            "stream": result.item.stream.value,
            "truncated": result.item.truncated,
        },
    )
    def __call__(
        self,
        job_id: str,
        *,
        stream: AttemptLogStream,
        lines: int,
        attempt_number: int | None = None,
    ) -> DetailResponse:
        with self._session_manager.session() as session:
            detail = self._job_service.get_job_log_tail(
                session,
                job_id=job_id,
                stream=stream,
                attempt_number=attempt_number,
            )
            tailed_lines, truncated = self._job_log_service.tail(path=detail.path, lines=lines)
            detail = detail.model_copy(update={"lines": tailed_lines, "truncated": truncated})
        return DetailResponse(item=detail)


class PruneJobsAction:
    """Prune terminal jobs and their associated history with dry-run support."""

    def __init__(
        self,
        session_manager: SessionManager,
        pruning_service: JobPruningService,
        job_log_service: JobLogService | None = None,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._pruning_service = pruning_service
        self._job_log_service = job_log_service or JobLogService()
        self._clock = clock

    @log_action(
        "prune_jobs",
        context_getter=lambda self, *, state, older_than, prune_logs, dry_run: {
            "state": state,
            "older_than": older_than,
            "prune_logs": prune_logs,
            "dry_run": dry_run,
        },
        result_getter=lambda result: {
            "dry_run": result.item.dry_run,
            "matched_job_count": result.item.matched_job_count,
            "deleted_job_count": result.item.deleted_job_count,
        },
    )
    def __call__(
        self,
        *,
        state: str | None,
        older_than: str | None,
        prune_logs: bool,
        dry_run: bool,
    ) -> MutationResponse:
        cutoff_at = self._parse_older_than(older_than) if older_than else None

        with self._session_manager.transaction() as session:
            result = self._pruning_service.prune(
                session,
                state_filter=state,
                cutoff_at=cutoff_at,
                prune_logs=prune_logs,
                dry_run=dry_run,
            )

        if not dry_run and prune_logs and result.deleted_log_paths:
            deleted_paths = self._job_log_service.delete_paths(paths=result.deleted_log_paths)
            result = result.model_copy(
                update={
                    "deleted_log_paths": deleted_paths,
                    "deleted_log_count": len(deleted_paths),
                }
            )

        return MutationResponse(
            item=result.model_copy(update={"older_than": older_than}),
        )

    def _parse_older_than(self, value: str) -> datetime:
        """Parse a duration string like '24h', '7d', '30m' into a cutoff datetime."""
        from datetime import timedelta

        unit = value[-1].lower()
        try:
            amount = int(value[:-1])
        except ValueError:
            raise ValueError(f"invalid duration: {value!r}; expected format like '24h', '7d', '30m'") from None

        if unit == "m":
            delta = timedelta(minutes=amount)
        elif unit == "h":
            delta = timedelta(hours=amount)
        elif unit == "d":
            delta = timedelta(days=amount)
        else:
            raise ValueError(f"unsupported duration unit: {unit!r}; use 'm' (minutes), 'h' (hours), or 'd' (days)")

        return self._clock() - delta


class PurgeJobsAction:
    """Delete queued or retry-scheduled jobs for one queue."""

    def __init__(self, session_manager: SessionManager, queue_service: QueueService) -> None:
        self._session_manager = session_manager
        self._queue_service = queue_service

    @log_action(
        "purge_jobs",
        context_getter=lambda self, queue: {"queue": queue},
        result_getter=lambda result: {
            "queue": result.item.queue,
            "deleted_count": result.item.deleted_count,
        },
    )
    def __call__(self, queue: str) -> MutationResponse:
        with self._session_manager.transaction() as session:
            item = self._queue_service.purge_jobs(session, queue=queue)
        return MutationResponse(item=item)
