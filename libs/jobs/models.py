"""Job, attempt, and event models owned by the jobs capability."""

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
    event_log_path: str | None = None


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


class JobLogLivenessView(BaseModel):
    """Filesystem liveness for one attempt log stream."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str | None = None
    size_bytes: int | None = None
    modified_at: datetime | None = None


class JobPaneView(BaseModel):
    """Concise monitor-pane view of one job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    queue: str
    state: JobState
    command: str
    worker_id: str | None = None
    attempt_number: int | None = None
    started_at: datetime | None = None
    elapsed_seconds: int | None = None
    process_status: str = "unknown"
    output_status: str
    stdout: JobLogLivenessView
    stderr: JobLogLivenessView


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
        if (
            self.created_after is not None
            and self.created_before is not None
            and self.created_after > self.created_before
        ):
            raise ValueError("created_after must be less than or equal to created_before")
        if (
            self.available_after is not None
            and self.available_before is not None
            and self.available_after > self.available_before
        ):
            raise ValueError("available_after must be less than or equal to available_before")
        return self


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


__all__ = (
    "AttemptLogStream",
    "AttemptState",
    "AttemptView",
    "DeleteJobResult",
    "EnqueueJobInput",
    "EventView",
    "JobDetail",
    "JobListFilters",
    "JobListSort",
    "JobLogLivenessView",
    "JobLogTailView",
    "JobPaneView",
    "JobPruneResult",
    "JobPruneSummary",
    "JobState",
    "JobSummary",
)
