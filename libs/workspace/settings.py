"""The model xqueue's configuration validates against.

One model, `extra="forbid"`, holding exactly what a configuration file may say.
It is the programmatic contract; `resources/config/config.default.yaml` states
the same defaults in the form an operator reads.

Everything here is *static*: what a file may declare. The paths a runtime
actually uses are `RuntimePaths`, derived from the workspace and then overridden
by whichever of these four fields were set.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from xqueue.workspace.models import ControllerConfig, QueueConfig, WorkerDefaults


class Settings(BaseModel):
    """Composed, validated configuration, before paths are derived."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Unset means "derive from the workspace", which is the normal case.
    database_path: Path | None = None
    log_root: Path | None = None
    runtime_root: Path | None = None
    state_root: Path | None = None

    queue: QueueConfig = Field(default_factory=QueueConfig)
    worker: WorkerDefaults = Field(default_factory=WorkerDefaults)
    controller: ControllerConfig = Field(default_factory=ControllerConfig)


__all__ = ["Settings"]
