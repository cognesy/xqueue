"""Domain models for static configuration and resolved runtime paths."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class RuntimePaths(BaseModel):
    """Resolved filesystem paths used by xqueue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    config_file: Path
    state_root: Path
    runtime_root: Path
    log_root: Path
    database_path: Path


class WorkerDefaults(BaseModel):
    """Static worker defaults loaded from configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    poll_interval_seconds: float = Field(default=1.0, gt=0)
    default_timeout_seconds: int = Field(default=3600, ge=1)
    cancel_grace_period_seconds: int = Field(default=10, ge=1)
    retry_delay_seconds: int = Field(default=5, ge=0)


class QueueConfig(BaseModel):
    """Static queue-facing configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    default_queue: str = Field(default="default", min_length=1)


class RestartPolicy(StrEnum):
    ALWAYS = "always"
    ON_FAILURE = "on-failure"
    NEVER = "never"


class ControllerPoolConfig(BaseModel):
    """Static configuration for one supervised worker pool."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    queues: list[str] = Field(min_length=1)
    concurrency: int = Field(default=1, ge=1)
    poll_interval_seconds: float | None = Field(default=None, gt=0)
    lease_seconds: int = Field(default=30, ge=1)
    restart_policy: RestartPolicy = RestartPolicy.ON_FAILURE
    default_timeout_seconds: int | None = Field(default=None, ge=1)


class ControllerConfig(BaseModel):
    """Static controller configuration loaded from YAML."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pools: dict[str, ControllerPoolConfig] = Field(default_factory=dict)


class StaticConfig(BaseModel):
    """Configuration loaded from static YAML."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    database_path: Path | None = None
    log_root: Path | None = None
    runtime_root: Path | None = None
    state_root: Path | None = None
    queue: QueueConfig = Field(default_factory=QueueConfig)
    worker: WorkerDefaults = Field(default_factory=WorkerDefaults)
    controller: ControllerConfig = Field(default_factory=ControllerConfig)


class EffectiveConfig(BaseModel):
    """Fully resolved configuration used by actions and services."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paths: RuntimePaths
    queue: QueueConfig
    worker: WorkerDefaults
    controller: ControllerConfig
