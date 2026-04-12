"""Domain-layer enums and view models for xqueue."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    CANCELED = "canceled"
    TIMED_OUT = "timed_out"
    DEAD = "dead"


class AttemptState(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    TIMED_OUT = "timed_out"


class AttemptLogStream(StrEnum):
    STDOUT = "stdout"
    STDERR = "stderr"


class JobListSort(StrEnum):
    CREATED_ASC = "created-asc"
    CREATED_DESC = "created-desc"
    AVAILABLE_ASC = "available-asc"
    AVAILABLE_DESC = "available-desc"
    PRIORITY_ASC = "priority-asc"
    PRIORITY_DESC = "priority-desc"


class WorkerState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    DRAINING = "draining"
    STOPPED = "stopped"


class QueueState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class ControllerState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    DRAINING = "draining"
    RESTARTING = "restarting"
    STOPPING = "stopping"
    STOPPED = "stopped"


class ServiceManagerKind(StrEnum):
    LAUNCHD = "launchd"
    SYSTEMD = "systemd"


class HealthStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


class AttemptView(BaseModel):
    """Operator-visible attempt history."""

    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    id: int | None = None
    attempt_number: int
    worker_id: str | None = None
    state: AttemptState
    started_at: datetime
    finished_at: datetime | None = None
    exit_code: int | None = None
    error: str | None = None
    cancellation_reason: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None


class AttemptLogPaths(BaseModel):
    """Deterministic log file locations for one attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stdout_path: str
    stderr_path: str


class ShellExecutionRequest(BaseModel):
    """Executable shell-command request for the runner service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command: str = Field(min_length=1)
    cwd: str | None = None
    env: dict[str, str] | None = None
    shell: bool = True
    timeout_seconds: int | None = Field(default=None, ge=1)


class ProcessExecutionResult(BaseModel):
    """Structured result of one subprocess execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command: str
    process_id: int | None = None
    process_group_id: int | None = None
    started_at: datetime
    finished_at: datetime
    exit_code: int | None = None
    canceled: bool = False
    timed_out: bool = False
    cancellation_reason: str | None = None
    stdout_path: str
    stderr_path: str


class StartedAttempt(BaseModel):
    """Structured data returned when a running attempt is created."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int
    attempt_number: int
    started_at: datetime
    stdout_path: str
    stderr_path: str


class JobSummary(BaseModel):
    """Stable job summary view for list responses."""

    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    id: str
    queue: str
    command: str
    state: JobState
    priority: int
    created_at: datetime
    available_at: datetime
    worker_id: str | None = None
    attempt_count: int = 0
    last_exit_code: int | None = None
    last_error: str | None = None


class JobDetail(JobSummary):
    """Detailed job view including execution metadata and attempts."""

    shell: bool
    cwd: str | None = None
    env: dict[str, Any] | None = None
    timeout_seconds: int | None = None
    max_attempts: int
    lease_expires_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    created_by: str | None = None
    attempts: list[AttemptView] = Field(default_factory=list)
    events: list["EventView"] = Field(default_factory=list)


class EventView(BaseModel):
    """Operator-visible event history."""

    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    id: int | None = None
    event_type: str
    created_at: datetime
    payload: dict[str, Any] | None = None


class QueueView(BaseModel):
    """Operator-visible queue state."""

    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    name: str
    state: QueueState
    paused_at: datetime | None = None


class QueueStatsView(QueueView):
    """Queue state plus per-state job counts."""

    total_jobs: int = 0
    queued_jobs: int = 0
    running_jobs: int = 0
    retry_scheduled_jobs: int = 0
    succeeded_jobs: int = 0
    failed_jobs: int = 0
    canceled_jobs: int = 0
    timed_out_jobs: int = 0
    dead_jobs: int = 0


class PurgeJobsResult(BaseModel):
    """Summary of a purge operation for one queue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    queue: str
    deleted_count: int


class DeleteJobResult(BaseModel):
    """Summary of one explicit job deletion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    deleted_state: JobState
    deleted_attempt_count: int = 0
    deleted_event_count: int = 0
    deleted_log_paths: list[str] = Field(default_factory=list)


class JobLogTailView(BaseModel):
    """Structured tail view for one attempt log file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    attempt_number: int
    stream: AttemptLogStream
    path: str
    lines: list[str] = Field(default_factory=list)
    truncated: bool = False


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


class JobPruneResult(BaseModel):
    """Summary of a job pruning operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dry_run: bool = True
    state_filter: str | None = None
    older_than: str | None = None
    cutoff_at: datetime | None = None
    matched_job_count: int = 0
    deleted_job_count: int = 0
    deleted_attempt_count: int = 0
    deleted_event_count: int = 0
    deleted_log_count: int = 0
    deleted_log_paths: list[str] = Field(default_factory=list)
    matched_jobs: list["JobPruneSummary"] = Field(default_factory=list)


class JobPruneSummary(BaseModel):
    """One job matched by a prune operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    queue: str
    state: JobState
    attempt_count: int = 0
    created_at: datetime


class WorkspaceInstanceResetResult(BaseModel):
    """Summary of a repo-local instance reset run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_root: str
    config_file: str
    removed_paths: list[str] = Field(default_factory=list)
    recreated_paths: list[str] = Field(default_factory=list)


class JobListFilters(BaseModel):
    """Supported filters for early operator job inspection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    queue: str | None = None
    state: JobState | None = None
    worker_id: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    available_after: datetime | None = None
    available_before: datetime | None = None
    sort: JobListSort = JobListSort.CREATED_DESC
    limit: int = Field(default=50, ge=1, le=500)

    @model_validator(mode="after")
    def validate_ranges(self) -> "JobListFilters":
        if self.created_after is not None and self.created_before is not None and self.created_after > self.created_before:
            raise ValueError("created_after must be less than or equal to created_before")
        if self.available_after is not None and self.available_before is not None and self.available_after > self.available_before:
            raise ValueError("available_after must be less than or equal to available_before")
        return self


class WorkerView(BaseModel):
    """Operator-visible worker view."""

    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    id: str
    state: WorkerState
    queues: list[str] = Field(default_factory=list)
    heartbeat_at: datetime | None = None
    started_at: datetime
    hostname: str | None = None
    process_id: int | None = None
    concurrency: int = 1


class ControllerWorkerView(BaseModel):
    """One supervised worker process inside a controller pool."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    worker_id: str
    pool_name: str
    process_id: int | None = None
    process_state: str
    restart_count: int = 0
    exit_code: int | None = None


class ControllerPoolView(BaseModel):
    """Operator-visible controller pool state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    queues: list[str] = Field(default_factory=list)
    concurrency: int = 1
    poll_interval_seconds: float
    restart_policy: str
    default_timeout_seconds: int | None = None
    workers: list[ControllerWorkerView] = Field(default_factory=list)


class ControllerStatusView(BaseModel):
    """Operator-visible controller status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    controller_id: str
    state: ControllerState
    process_id: int | None = None
    config_path: str
    started_at: datetime | None = None
    updated_at: datetime | None = None
    pools: list[ControllerPoolView] = Field(default_factory=list)


class ControllerCommandResult(BaseModel):
    """Acknowledgement of a controller control request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    controller_id: str
    requested_state: ControllerState
    control_path: str


class ManagedControllerInstallView(BaseModel):
    """Summary of a managed controller installation or lifecycle mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manager: ServiceManagerKind
    controller_id: str
    service_name: str
    artifact_path: str
    action: str


class ManagedControllerStatusView(BaseModel):
    """Status of a managed controller service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manager: ServiceManagerKind
    controller_id: str
    service_name: str
    artifact_path: str
    installed: bool
    loaded: bool
    active: bool
    details: str | None = None


class RegisterWorkerInput(BaseModel):
    """Validated input for worker registration or refresh."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    worker_id: str = Field(min_length=1)
    queues: list[str] = Field(min_length=1)
    concurrency: int = Field(default=1, ge=1)
    hostname: str | None = None
    process_id: int | None = None
    state: WorkerState = WorkerState.ACTIVE


class WorkerPollResult(BaseModel):
    """Result of a single worker poll iteration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    worker: WorkerView
    claimed_job: JobDetail | None = None


class EnqueueJobInput(BaseModel):
    """Validated input for durable job creation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    queue: str = Field(min_length=1)
    command: str = Field(min_length=1)
    shell: bool = True
    cwd: str | None = None
    env: dict[str, str] | None = None
    priority: int = 100
    timeout_seconds: int | None = Field(default=None, ge=1)
    max_attempts: int = Field(default=1, ge=1)
    created_by: str | None = None
    available_at: datetime | None = None

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("command must not be empty")
        return stripped
