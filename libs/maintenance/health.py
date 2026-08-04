"""Operational health and diagnostic read model."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
from xqueue.adapters.sqlite.models import WorkerModel
from xqueue.maintenance.models import DatabaseCheckResult, DoctorCheck, DoctorReport, HealthReport, HealthStatus
from xqueue.maintenance.recovery import RecoveryService
from xqueue.queues.store import QueueService
from xqueue.workers.models import WorkerState, WorkerView
from xqueue.workers.store import WorkerService


class HealthService:
    """Summarize operator-visible system health."""

    def __init__(
        self,
        *,
        queue_service: QueueService | None = None,
        recovery_service: RecoveryService | None = None,
        worker_service: WorkerService | None = None,
    ) -> None:
        self._queue_service = queue_service or QueueService()
        self._recovery_service = recovery_service or RecoveryService()
        self._worker_service = worker_service or WorkerService()

    def collect_health(
        self,
        session: Session | None,
        *,
        now: datetime,
        database_check: DatabaseCheckResult,
        worker_stale_after_seconds: int,
    ) -> HealthReport:
        paused_queues: list[str] = []
        stale_leases = []
        stale_workers: list[WorkerView] = []

        if session is not None and database_check.status is not HealthStatus.ERROR:
            paused_queues = [
                item.name for item in self._queue_service.list_queues(session) if item.state.value == "paused"
            ]
            stale_leases = self._recovery_service.list_stale_leases(session, now=now)
            stale_workers = self._list_stale_workers(
                session,
                now=now,
                worker_stale_after_seconds=worker_stale_after_seconds,
            )

        status = database_check.status
        if status is not HealthStatus.ERROR and (paused_queues or stale_leases or stale_workers):
            status = HealthStatus.WARN

        return HealthReport(
            status=status,
            database_status=database_check.status,
            database_message=self._database_message(database_check),
            paused_queues=paused_queues,
            stale_leases=stale_leases,
            stale_workers=stale_workers,
        )

    def collect_doctor(
        self,
        session: Session | None,
        *,
        now: datetime,
        database_check: DatabaseCheckResult,
        worker_stale_after_seconds: int,
    ) -> DoctorReport:
        checks = [
            DoctorCheck(
                name="database.integrity",
                status=database_check.status,
                summary=self._database_message(database_check),
                details={
                    "database_path": database_check.database_path,
                    "integrity_result": database_check.integrity_result,
                    "missing_tables": database_check.missing_tables,
                },
            )
        ]

        if session is not None and database_check.status is not HealthStatus.ERROR:
            paused_queues = [
                item.name for item in self._queue_service.list_queues(session) if item.state.value == "paused"
            ]
            stale_leases = self._recovery_service.list_stale_leases(session, now=now)
            stale_workers = self._list_stale_workers(
                session,
                now=now,
                worker_stale_after_seconds=worker_stale_after_seconds,
            )
        else:
            paused_queues = []
            stale_leases = []
            stale_workers = []

        checks.append(
            DoctorCheck(
                name="queues.paused",
                status=HealthStatus.WARN if paused_queues else HealthStatus.OK,
                summary="paused queues detected" if paused_queues else "no paused queues",
                details={"queues": paused_queues},
            )
        )
        checks.append(
            DoctorCheck(
                name="leases.stale",
                status=HealthStatus.WARN if stale_leases else HealthStatus.OK,
                summary="stale leases detected" if stale_leases else "no stale leases",
                details={"job_ids": [item.job_id for item in stale_leases]},
            )
        )
        checks.append(
            DoctorCheck(
                name="workers.heartbeat",
                status=HealthStatus.WARN if stale_workers else HealthStatus.OK,
                summary="stale worker heartbeats detected" if stale_workers else "worker heartbeats look healthy",
                details={"worker_ids": [item.id for item in stale_workers]},
            )
        )

        statuses = {check.status for check in checks}
        if HealthStatus.ERROR in statuses:
            status = HealthStatus.ERROR
        elif HealthStatus.WARN in statuses:
            status = HealthStatus.WARN
        else:
            status = HealthStatus.OK

        return DoctorReport(status=status, checks=checks)

    def _list_stale_workers(
        self,
        session: Session,
        *,
        now: datetime,
        worker_stale_after_seconds: int,
    ) -> list[WorkerView]:
        cutoff = now - timedelta(seconds=worker_stale_after_seconds)
        models = (
            session.execute(
                select(WorkerModel)
                .where(
                    WorkerModel.state.in_(
                        [WorkerState.ACTIVE.value, WorkerState.PAUSED.value, WorkerState.DRAINING.value]
                    )
                )
                .where((WorkerModel.heartbeat_at.is_(None)) | (WorkerModel.heartbeat_at < cutoff))
                .order_by(WorkerModel.heartbeat_at.asc(), WorkerModel.id.asc())
            )
            .scalars()
            .all()
        )
        return [self._worker_service.to_worker_view(model) for model in models]

    def _database_message(self, database_check: DatabaseCheckResult) -> str:
        if database_check.missing_tables:
            missing = ", ".join(database_check.missing_tables)
            return f"database schema is missing tables: {missing}"
        if database_check.integrity_result != "ok":
            return f"database integrity check returned {database_check.integrity_result}"
        return "database integrity and schema look healthy"
