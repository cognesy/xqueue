"""Controller and service-manager models owned by the controller capability."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


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


class ControllerPoolConfigView(BaseModel):
    """Static controller pool configuration exposed by pool-management commands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    queues: list[str] = Field(default_factory=list)
    concurrency: int = 1
    poll_interval_seconds: float | None = None
    lease_seconds: int = 30
    restart_policy: str
    default_timeout_seconds: int | None = None


class ControllerPoolMutationResult(BaseModel):
    """Summary of one controller pool config mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: str
    name: str
    pool: ControllerPoolConfigView | None = None
    config_path: str
    restart_required: bool


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


__all__ = (
    "ControllerCommandResult",
    "ControllerPoolConfigView",
    "ControllerPoolMutationResult",
    "ControllerPoolView",
    "ControllerState",
    "ControllerStatusView",
    "ControllerWorkerView",
    "ManagedControllerInstallView",
    "ManagedControllerStatusView",
    "ServiceManagerKind",
)
