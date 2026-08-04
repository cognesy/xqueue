"""Worker and process-execution models owned by the workers capability."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from xqueue.jobs.models import JobDetail


class WorkerState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    DRAINING = "draining"
    STOPPED = "stopped"


class AttemptLogPaths(BaseModel):
    """Deterministic log file locations for one attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stdout_path: str
    stderr_path: str
    event_log_path: str


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
    event_log_path: str


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


__all__ = (
    "AttemptLogPaths",
    "ProcessExecutionResult",
    "RegisterWorkerInput",
    "ShellExecutionRequest",
    "StartedAttempt",
    "WorkerPollResult",
    "WorkerState",
    "WorkerView",
)
