"""Typed static and effective workspace configuration."""

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


class HookInstallItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    executable_path: str
    changed_files: list[str] = Field(default_factory=list)


class ClaudeHookStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    settings_path: str
    settings_exists: bool
    session_start_matches: bool
    stop_matches: bool


class CodexHookStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    config_path: str
    hooks_path: str
    config_exists: bool
    hooks_exists: bool
    feature_enabled: bool
    session_start_matches: bool
    session_end_matches: bool


class HookStatusItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    executable_path: str
    claude: ClaudeHookStatus
    codex: CodexHookStatus


class SessionCaptureItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    log_path: str


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


class ConfigLayer(BaseModel):
    """One source in the configuration precedence chain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    layer: str
    origin: str
    applied: bool


class EffectiveConfig(BaseModel):
    """Fully resolved configuration used by actions and services.

    `layers` records the precedence chain that produced this, base first, so
    `xq config show` can answer "where did this value come from" without the
    operator reconstructing the order from documentation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    paths: RuntimePaths
    queue: QueueConfig
    worker: WorkerDefaults
    controller: ControllerConfig
    layers: list[ConfigLayer] = Field(default_factory=list)


class WorkspaceInitResult(BaseModel):
    """What `workspace init` changed, retained, and refused to touch.

    A typed change set rather than a boolean: an idempotent command has to be
    able to say "nothing to do" and "I left your config alone" distinctly, or
    running it twice looks like a failure.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    root: str
    directory: str
    scope: str
    created_paths: list[str] = Field(default_factory=list)
    retained_paths: list[str] = Field(default_factory=list)
    conflicting_paths: list[str] = Field(default_factory=list)


class WorkspaceInstanceResetResult(BaseModel):
    """Summary of a repo-local instance reset run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_root: str
    config_file: str
    removed_paths: list[str] = Field(default_factory=list)
    recreated_paths: list[str] = Field(default_factory=list)
