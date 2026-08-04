"""Job capability actions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from xqueue.adapters.filesystem.metrics import MetricsService
from xqueue.adapters.sqlite.session import SessionManager
from xqueue.jobs.logs import JobLogService
from xqueue.jobs.models import (
    AttemptLogStream,
    DeleteJobResult,
    EnqueueJobInput,
    JobDetail,
    JobListFilters,
    JobLogLivenessView,
    JobLogTailView,
    JobPaneView,
    JobPruneResult,
    JobState,
    JobSummary,
)
from xqueue.jobs.ports import JobLogPort
from xqueue.jobs.pruning import JobPruningService
from xqueue.jobs.store import JobService
from xqueue.runtime.action_logging import log_action


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
        metrics: MetricsService,
        clock: Callable[[], datetime] = utc_now,
        id_factory: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        self._session_manager = session_manager
        self._job_service = job_service
        self._clock = clock
        self._id_factory = id_factory
        self._metrics = metrics

    @log_action(
        "enqueue_job",
        context_getter=lambda self, payload: {
            "queue": payload.queue,
            "priority": payload.priority,
            "max_attempts": payload.max_attempts,
            "has_timeout": payload.timeout_seconds is not None,
        },
        result_getter=lambda result: {
            "job_id": result.id,
            "job_state": result.state.value,
        },
    )
    def __call__(self, payload: EnqueueJobInput) -> JobDetail:
        with self._session_manager.transaction() as session:
            item = self._job_service.enqueue(
                session,
                job_id=self._id_factory(),
                payload=payload,
                now=self._clock(),
            )
        self._metrics.increment("jobs.enqueued")
        return item


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
            "item_count": len(result),
        },
    )
    def __call__(self, filters: JobListFilters) -> list[JobSummary]:
        with self._session_manager.session() as session:
            items = self._job_service.list_jobs(session, filters=filters)
        return items


class ShowJobAction:
    """Return a detailed view of a single job."""

    def __init__(self, session_manager: SessionManager, job_service: JobService) -> None:
        self._session_manager = session_manager
        self._job_service = job_service

    @log_action(
        "show_job",
        context_getter=lambda self, job_id: {"job_id": job_id},
        result_getter=lambda result: {
            "job_id": result.id,
            "job_state": result.state.value,
        },
    )
    def __call__(self, job_id: str) -> JobDetail:
        with self._session_manager.session() as session:
            item = self._job_service.get_job(session, job_id=job_id)
        return item


class JobPaneAction:
    """Return a concise monitor-pane view of one job."""

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
        "job_pane",
        context_getter=lambda self, job_id: {"job_id": job_id},
        result_getter=lambda result: {"job_id": result.id, "job_state": result.state.value},
    )
    def __call__(self, job_id: str) -> JobPaneView:
        with self._session_manager.session() as session:
            job = self._job_service.get_job(session, job_id=job_id)

        attempt = job.attempts[-1] if job.attempts else None
        stdout = self._log_liveness(None if attempt is None else attempt.stdout_path)
        stderr = self._log_liveness(None if attempt is None else attempt.stderr_path)
        item = JobPaneView(
            id=job.id,
            queue=job.queue,
            state=job.state,
            command=job.command,
            worker_id=job.worker_id,
            attempt_number=None if attempt is None else attempt.attempt_number,
            started_at=None if attempt is None else attempt.started_at,
            elapsed_seconds=self._elapsed_seconds(
                None if attempt is None else attempt.started_at, None if attempt is None else attempt.finished_at
            ),
            process_status="unknown" if job.state is JobState.RUNNING else "not_running",
            output_status=self._output_status(stdout, stderr),
            stdout=stdout,
            stderr=stderr,
        )
        return item

    def _log_liveness(self, path: str | None) -> JobLogLivenessView:
        if path is None:
            return JobLogLivenessView()
        log_path = Path(path)
        if not log_path.exists():
            return JobLogLivenessView(path=path)
        stat = log_path.stat()
        return JobLogLivenessView(
            path=path,
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )

    def _elapsed_seconds(self, started_at: datetime | None, finished_at: datetime | None) -> int | None:
        if started_at is None:
            return None
        end = finished_at or self._clock()
        return max(0, int((end - started_at).total_seconds()))

    def _output_status(self, stdout: JobLogLivenessView, stderr: JobLogLivenessView) -> str:
        stdout_size = stdout.size_bytes or 0
        stderr_size = stderr.size_bytes or 0
        if stdout_size or stderr_size:
            return f"stdout={stdout_size}B stderr={stderr_size}B"
        return "no output yet"


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
            "job_id": result.id,
            "job_state": result.state.value,
            "cancel_requested": result.cancel_requested_at is not None,
        },
    )
    def __call__(self, job_id: str) -> JobDetail:
        with self._session_manager.transaction() as session:
            item = self._job_service.cancel_job(session, job_id=job_id, now=self._clock())
        return item


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
            "job_id": result.id,
            "job_state": result.state.value,
            "attempt_count": result.attempt_count,
        },
    )
    def __call__(self, job_id: str) -> JobDetail:
        with self._session_manager.transaction() as session:
            item = self._job_service.retry_job(session, job_id=job_id, now=self._clock())
        return item


class DeleteJobAction:
    """Delete a non-running job and its associated history."""

    def __init__(
        self,
        session_manager: SessionManager,
        job_service: JobService,
        job_log_service: JobLogPort | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._job_service = job_service
        self._job_log_service = job_log_service or JobLogService()

    @log_action(
        "delete_job",
        context_getter=lambda self, job_id: {"job_id": job_id},
        result_getter=lambda result: {
            "job_id": result.job_id,
            "deleted_state": result.deleted_state.value,
            "deleted_attempt_count": result.deleted_attempt_count,
        },
    )
    def __call__(self, job_id: str) -> DeleteJobResult:
        with self._session_manager.transaction() as session:
            item = self._job_service.delete_job(session, job_id=job_id)

        deleted_log_paths = self._job_log_service.delete_paths(paths=item.deleted_log_paths)
        return item.model_copy(update={"deleted_log_paths": deleted_log_paths})


class TailJobLogsAction:
    """Return a structured tail view for one attempt log stream."""

    def __init__(
        self,
        session_manager: SessionManager,
        job_service: JobService,
        job_log_service: JobLogPort | None = None,
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
            "job_id": result.job_id,
            "attempt_number": result.attempt_number,
            "stream": result.stream.value,
            "truncated": result.truncated,
        },
    )
    def __call__(
        self,
        job_id: str,
        *,
        stream: AttemptLogStream,
        lines: int,
        attempt_number: int | None = None,
    ) -> JobLogTailView:
        with self._session_manager.session() as session:
            detail = self._job_service.get_job_log_tail(
                session,
                job_id=job_id,
                stream=stream,
                attempt_number=attempt_number,
            )
            tailed_lines, truncated = self._job_log_service.tail(path=detail.path, lines=lines)
            detail = detail.model_copy(update={"lines": tailed_lines, "truncated": truncated})
        return detail


class PruneJobsAction:
    """Prune terminal jobs and their associated history with dry-run support."""

    def __init__(
        self,
        session_manager: SessionManager,
        pruning_service: JobPruningService,
        job_log_service: JobLogPort | None = None,
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
            "dry_run": result.dry_run,
            "matched_job_count": result.matched_job_count,
            "deleted_job_count": result.deleted_job_count,
        },
    )
    def __call__(
        self,
        *,
        state: str | None,
        older_than: str | None,
        prune_logs: bool,
        dry_run: bool,
    ) -> JobPruneResult:
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

        return result.model_copy(update={"older_than": older_than})

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
