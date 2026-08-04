"""Maintenance SDK facet."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from xqueue.core.errors import StateStoreUnavailableError
from xqueue.jobs.models import JobState
from xqueue.maintenance.models import (
    DatabaseCheckResult,
    DatabaseVacuumResult,
    DoctorReport,
    HealthReport,
    HomeJobCount,
    HomeQueueRow,
    HomeSnapshot,
    HomeWorkerRow,
    RecoverStaleLeasesResult,
    RetentionCleanupResult,
    RuntimeMetricsResetView,
    RuntimeMetricsView,
)
from xqueue.workers.models import WorkerState

if TYPE_CHECKING:
    from xqueue.runtime.composition import Runtime


class Maintenance:
    """Read operational health from the shared runtime."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def health(self) -> HealthReport:
        self._runtime.ensure_open()
        return self._runtime.maintenance_actions.health()

    def doctor(self) -> DoctorReport:
        self._runtime.ensure_open()
        return self._runtime.maintenance_actions.doctor()

    def check_database(self) -> DatabaseCheckResult:
        self._runtime.ensure_open()
        return self._runtime.maintenance_actions.check_database()

    def vacuum_database(self) -> DatabaseVacuumResult:
        self._runtime.ensure_open()
        return self._runtime.maintenance_actions.vacuum_database()

    def cleanup_retention(
        self,
        *,
        older_than_hours: int,
        prune_attempts: bool = True,
        prune_events: bool = True,
        prune_logs: bool = True,
    ) -> RetentionCleanupResult:
        self._runtime.ensure_open()
        return self._runtime.maintenance_actions.cleanup_retention(
            older_than_hours=older_than_hours,
            prune_attempts=prune_attempts,
            prune_events=prune_events,
            prune_logs=prune_logs,
        )

    def recover_stale_leases(self, *, retry_delay_seconds: int | None = None) -> RecoverStaleLeasesResult:
        self._runtime.ensure_open()
        return self._runtime.maintenance_actions.recover_stale_leases(retry_delay_seconds)

    def metrics(self) -> RuntimeMetricsView:
        self._runtime.ensure_open()
        return self._runtime.maintenance_actions.show_metrics()

    def reset_metrics(self) -> RuntimeMetricsResetView:
        self._runtime.ensure_open()
        return self._runtime.maintenance_actions.reset_metrics()

    def home(self) -> HomeSnapshot:
        """Read the compact operator overview; the channel owns its presentation."""
        self._runtime.ensure_open()
        state_store_available = True
        try:
            queue_stats = self._runtime.queue_actions.stats()
            workers = self._runtime.worker_actions.list()
            worker_commands = self._runtime.worker_actions.running_commands()
        except StateStoreUnavailableError as exc:
            # A workspace with no database yet must still render; anything else
            # propagates to the CLI error path rather than showing a healthy-looking
            # empty screen.
            structlog.get_logger("xqueue.maintenance").info(
                "home.state_store_unavailable",
                error=exc.message,
            )
            queue_stats = []
            workers = []
            worker_commands = {}
            state_store_available = False

        job_counts = {
            JobState.QUEUED: 0,
            JobState.RUNNING: 0,
            JobState.RETRY_SCHEDULED: 0,
            JobState.SUCCEEDED: 0,
            JobState.FAILED: 0,
            JobState.CANCELED: 0,
        }
        for queue in queue_stats:
            job_counts[JobState.QUEUED] += queue.queued_jobs
            job_counts[JobState.RUNNING] += queue.running_jobs
            job_counts[JobState.RETRY_SCHEDULED] += queue.retry_scheduled_jobs
            job_counts[JobState.SUCCEEDED] += queue.succeeded_jobs
            job_counts[JobState.FAILED] += queue.failed_jobs
            job_counts[JobState.CANCELED] += queue.canceled_jobs

        return HomeSnapshot(
            queues=[
                HomeQueueRow(
                    name=queue.name,
                    state=queue.state,
                    total_jobs=queue.total_jobs,
                    running_jobs=queue.running_jobs,
                    queued_jobs=queue.queued_jobs,
                )
                for queue in queue_stats
            ],
            jobs=[HomeJobCount(state=state, count=count) for state, count in job_counts.items()],
            workers=[
                HomeWorkerRow(
                    id=worker.id,
                    state=worker.state,
                    queues=list(worker.queues),
                    heartbeat_at=None if worker.heartbeat_at is None else worker.heartbeat_at.isoformat(),
                    current_command=worker_commands.get(worker.id),
                )
                for worker in workers
                if worker.state is WorkerState.ACTIVE
            ],
            state_store_available=state_store_available,
        )
