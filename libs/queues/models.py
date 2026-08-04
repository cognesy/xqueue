"""Queue models owned by the queues capability."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class QueueState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


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


__all__ = (
    "PurgeJobsResult",
    "QueueState",
    "QueueStatsView",
    "QueueView",
)
