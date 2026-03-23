"""Operational health and database maintenance actions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from libs.actions.logging import log_action
from libs.domain.errors import ValidationError
from libs.domain.config import RuntimePaths
from libs.domain.responses import DetailResponse, MutationResponse
from libs.services.database import SessionManager
from libs.services.database_maintenance import DatabaseMaintenanceService
from libs.services.health import HealthService
from libs.services.job_logs import JobLogService
from libs.services.retention import RetentionCleanupService
from libs.services.workspace_instance import WorkspaceInstanceService


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class HealthAction:
    """Return a high-level health summary."""

    def __init__(
        self,
        session_manager: SessionManager,
        health_service: HealthService,
        database_service: DatabaseMaintenanceService,
        *,
        worker_stale_after_seconds: int = 60,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._health_service = health_service
        self._database_service = database_service
        self._worker_stale_after_seconds = worker_stale_after_seconds
        self._clock = clock

    @log_action(
        "health",
        context_getter=lambda self: {"worker_stale_after_seconds": self._worker_stale_after_seconds},
        result_getter=lambda result: {"status": result.item.status.value},
    )
    def __call__(self) -> DetailResponse:
        now = self._clock()
        database_check = self._database_service.check()
        if database_check.status.value == "error":
            item = self._health_service.collect_health(
                None,
                now=now,
                database_check=database_check,
                worker_stale_after_seconds=self._worker_stale_after_seconds,
            )
            return DetailResponse(item=item)

        with self._session_manager.session() as session:
            item = self._health_service.collect_health(
                session,
                now=now,
                database_check=database_check,
                worker_stale_after_seconds=self._worker_stale_after_seconds,
            )
        return DetailResponse(item=item)


class DoctorAction:
    """Return a detailed diagnostic report."""

    def __init__(
        self,
        session_manager: SessionManager,
        health_service: HealthService,
        database_service: DatabaseMaintenanceService,
        *,
        worker_stale_after_seconds: int = 60,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._health_service = health_service
        self._database_service = database_service
        self._worker_stale_after_seconds = worker_stale_after_seconds
        self._clock = clock

    @log_action(
        "doctor",
        context_getter=lambda self: {"worker_stale_after_seconds": self._worker_stale_after_seconds},
        result_getter=lambda result: {"status": result.item.status.value, "check_count": len(result.item.checks)},
    )
    def __call__(self) -> DetailResponse:
        now = self._clock()
        database_check = self._database_service.check()
        if database_check.status.value == "error":
            item = self._health_service.collect_doctor(
                None,
                now=now,
                database_check=database_check,
                worker_stale_after_seconds=self._worker_stale_after_seconds,
            )
            return DetailResponse(item=item)

        with self._session_manager.session() as session:
            item = self._health_service.collect_doctor(
                session,
                now=now,
                database_check=database_check,
                worker_stale_after_seconds=self._worker_stale_after_seconds,
            )
        return DetailResponse(item=item)


class CheckDatabaseAction:
    """Run an integrity and schema readiness check."""

    def __init__(self, database_service: DatabaseMaintenanceService) -> None:
        self._database_service = database_service

    @log_action(
        "db_check",
        result_getter=lambda result: {"status": result.item.status.value, "missing_tables": result.item.missing_tables},
    )
    def __call__(self) -> DetailResponse:
        return DetailResponse(item=self._database_service.check())


class VacuumDatabaseAction:
    """Run SQLite VACUUM."""

    def __init__(self, database_service: DatabaseMaintenanceService) -> None:
        self._database_service = database_service

    @log_action(
        "db_vacuum",
        result_getter=lambda result: {
            "database_path": result.item.database_path,
            "size_before_bytes": result.item.size_before_bytes,
            "size_after_bytes": result.item.size_after_bytes,
        },
    )
    def __call__(self) -> MutationResponse:
        return MutationResponse(item=self._database_service.vacuum())


class ResetWorkspaceInstanceAction:
    """Reset repo-local runtime artifacts under the workspace instance tree."""

    def __init__(self, workspace_instance_service: WorkspaceInstanceService) -> None:
        self._workspace_instance_service = workspace_instance_service

    @log_action(
        "reset_workspace_instance",
        context_getter=lambda self, paths, alembic_ini_path: {
            "state_root": str(paths.state_root),
            "alembic_ini_path": str(alembic_ini_path),
        },
        result_getter=lambda result: {
            "state_root": result.item.state_root,
            "removed_path_count": len(result.item.removed_paths),
            "recreated_path_count": len(result.item.recreated_paths),
        },
    )
    def __call__(self, paths: RuntimePaths, *, alembic_ini_path) -> MutationResponse:
        return MutationResponse(item=self._workspace_instance_service.reset(paths=paths, alembic_ini_path=alembic_ini_path))


class CleanupRetentionAction:
    """Run explicit retention cleanup for old attempts, events, and logs."""

    def __init__(
        self,
        session_manager: SessionManager,
        retention_cleanup_service: RetentionCleanupService,
        job_log_service: JobLogService | None = None,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._retention_cleanup_service = retention_cleanup_service
        self._job_log_service = job_log_service or JobLogService()
        self._clock = clock

    @log_action(
        "cleanup_retention",
        context_getter=lambda self, *, older_than_hours, prune_attempts, prune_events, prune_logs: {
            "older_than_hours": older_than_hours,
            "prune_attempts": prune_attempts,
            "prune_events": prune_events,
            "prune_logs": prune_logs,
        },
        result_getter=lambda result: {
            "deleted_attempt_count": result.item.deleted_attempt_count,
            "deleted_event_count": result.item.deleted_event_count,
            "deleted_log_count": result.item.deleted_log_count,
        },
    )
    def __call__(
        self,
        *,
        older_than_hours: int,
        prune_attempts: bool,
        prune_events: bool,
        prune_logs: bool,
    ) -> MutationResponse:
        if not any([prune_attempts, prune_events, prune_logs]):
            raise ValidationError("cleanup-retention requires at least one selected artifact class")

        cutoff_at = self._clock() - timedelta(hours=older_than_hours)
        with self._session_manager.transaction() as session:
            item = self._retention_cleanup_service.cleanup(
                session,
                cutoff_at=cutoff_at,
                prune_attempts=prune_attempts,
                prune_events=prune_events,
                prune_logs=prune_logs,
            )

        deleted_log_paths = self._job_log_service.delete_paths(paths=item.deleted_log_paths)
        return MutationResponse(
            item=item.model_copy(
                update={
                    "deleted_log_paths": deleted_log_paths,
                    "deleted_log_count": len(deleted_log_paths),
                }
            )
        )
