"""Stable response envelopes for CLI output."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from xqueue_libs.domain.models import JobState, QueueState, WorkerState


T = TypeVar("T")


class PayloadConvertible(BaseModel):
    """Base model for values that can be rendered by the CLI output layer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable payload for structured formats."""
        return self.model_dump(mode="json")

    def jsonl_items(self) -> list[Any] | None:
        """Return JSONL rows when the response has a natural item stream."""
        return None


class ErrorDetail(BaseModel):
    """Structured error payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ListResponse(PayloadConvertible, Generic[T]):
    """Stable envelope for list commands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[T]
    meta: dict[str, Any] | None = None

    def jsonl_items(self) -> list[Any] | None:
        """Emit list items as JSONL rows."""
        return list(self.items)


class DetailResponse(PayloadConvertible, Generic[T]):
    """Stable envelope for detail commands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item: T


class MutationResponse(PayloadConvertible, Generic[T]):
    """Stable envelope for successful mutations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool = True
    item: T


class ErrorResponse(PayloadConvertible):
    """Stable envelope for failures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool = False
    error: ErrorDetail


class HomeQueueRow(BaseModel):
    """Compact queue summary row for the home view."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    state: QueueState
    total_jobs: int = 0
    running_jobs: int = 0
    queued_jobs: int = 0


class HomeJobCount(BaseModel):
    """Aggregate job count row for the home view."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: JobState
    count: int


class HomeWorkerRow(BaseModel):
    """Compact worker summary row for the home view."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: WorkerState
    queues: list[str] = Field(default_factory=list)
    heartbeat_at: str | None = None
    current_command: str | None = None


class HomeResponse(PayloadConvertible):
    """Content-first top-level response for bare xq invocations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bin: str
    description: str
    queues: list[HomeQueueRow] = Field(default_factory=list)
    jobs: list[HomeJobCount] = Field(default_factory=list)
    workers: list[HomeWorkerRow] = Field(default_factory=list)
    help: list[str] = Field(default_factory=list)


class HookInstallItem(BaseModel):
    """Summary of a hook installation run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    executable_path: str
    changed_files: list[str] = Field(default_factory=list)


class ClaudeHookStatus(BaseModel):
    """Claude Code hook installation status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    settings_path: str
    settings_exists: bool
    session_start_matches: bool
    stop_matches: bool


class CodexHookStatus(BaseModel):
    """Codex hook installation status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    config_path: str
    hooks_path: str
    config_exists: bool
    hooks_exists: bool
    feature_enabled: bool
    session_start_matches: bool
    session_end_matches: bool


class HookStatusItem(BaseModel):
    """Combined session-hook installation status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    executable_path: str
    claude: ClaudeHookStatus
    codex: CodexHookStatus


class SessionCaptureItem(BaseModel):
    """Summary of one hook session-end capture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    log_path: str
