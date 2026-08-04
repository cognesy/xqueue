"""Health, diagnostics, metrics, and retention models owned by maintenance."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from xqueue.jobs.models import JobState
from xqueue.queues.models import QueueState
from xqueue.workers.models import WorkerState, WorkerView


class HealthStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


class RuntimeMetricsView(BaseModel):
    """Persisted runtime metrics visible to operators."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    version: int = 1
    created_at: str
    updated_at: str
    counters: dict[str, int] = Field(default_factory=dict)


class RuntimeMetricsResetView(RuntimeMetricsView):
    """Runtime metrics reset acknowledgement."""

    previous_counters: dict[str, int] = Field(default_factory=dict)


class StaleLeaseView(BaseModel):
    """Operator-visible stale lease candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    queue: str
    worker_id: str | None = None
    lease_expires_at: datetime
    attempt_count: int


class RecoveredLeaseView(BaseModel):
    """Summary of one stale lease recovery outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    queue: str
    previous_worker_id: str | None = None
    attempt_id: int | None = None
    recovered_at: datetime
    new_state: JobState
    available_at: datetime | None = None


class RecoverStaleLeasesResult(BaseModel):
    """Summary of one stale lease recovery run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recovered_count: int
    items: list[RecoveredLeaseView] = Field(default_factory=list)


class HealthReport(BaseModel):
    """High-level operational health summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: HealthStatus
    database_status: HealthStatus
    database_message: str
    paused_queues: list[str] = Field(default_factory=list)
    stale_leases: list[StaleLeaseView] = Field(default_factory=list)
    stale_workers: list["WorkerView"] = Field(default_factory=list)


class DoctorCheck(BaseModel):
    """One actionable diagnostic check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    status: HealthStatus
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class DoctorReport(BaseModel):
    """Detailed diagnostic report for operators."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: HealthStatus
    checks: list[DoctorCheck] = Field(default_factory=list)


class DatabaseCheckResult(BaseModel):
    """Integrity and schema readiness summary for the SQLite database."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: HealthStatus
    database_path: str
    integrity_result: str
    required_tables: list[str] = Field(default_factory=list)
    missing_tables: list[str] = Field(default_factory=list)


class DatabaseVacuumResult(BaseModel):
    """Summary of a VACUUM maintenance run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    database_path: str
    size_before_bytes: int | None = None
    size_after_bytes: int | None = None


class RetentionCleanupResult(BaseModel):
    """Summary of one explicit retention cleanup run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cutoff_at: datetime
    pruned_attempts: bool = False
    pruned_events: bool = False
    pruned_logs: bool = False
    deleted_attempt_count: int = 0
    deleted_event_count: int = 0
    deleted_log_count: int = 0
    deleted_log_paths: list[str] = Field(default_factory=list)


class HomeQueueRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    state: QueueState
    total_jobs: int = 0
    running_jobs: int = 0
    queued_jobs: int = 0


class HomeJobCount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: JobState
    count: int


class HomeWorkerRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: WorkerState
    queues: list[str] = Field(default_factory=list)
    heartbeat_at: str | None = None
    current_command: str | None = None


class HomeSnapshot(BaseModel):
    """Facts behind the compact operator overview; no channel presentation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    queues: list[HomeQueueRow] = Field(default_factory=list)
    jobs: list[HomeJobCount] = Field(default_factory=list)
    workers: list[HomeWorkerRow] = Field(default_factory=list)
    state_store_available: bool = True


__all__ = (
    "DatabaseCheckResult",
    "DatabaseVacuumResult",
    "DoctorCheck",
    "DoctorReport",
    "HealthReport",
    "HealthStatus",
    "HomeJobCount",
    "HomeQueueRow",
    "HomeSnapshot",
    "HomeWorkerRow",
    "RecoverStaleLeasesResult",
    "RecoveredLeaseView",
    "RetentionCleanupResult",
    "RuntimeMetricsResetView",
    "RuntimeMetricsView",
    "StaleLeaseView",
)
