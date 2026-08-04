"""Ports for managed controller platform adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from xqueue.controller.models import ManagedControllerInstallView, ManagedControllerStatusView


class ManagedControllerPort(Protocol):
    """Owned-artifact operations supplied by launchd or systemd --user."""

    def install(
        self,
        *,
        controller_id: str,
        workspace_root: Path,
        config_path: Path,
        log_root: Path,
        use_workspace_instance: bool,
    ) -> ManagedControllerInstallView: ...

    def uninstall(self, *, controller_id: str) -> ManagedControllerInstallView: ...

    def start(self, *, controller_id: str) -> ManagedControllerInstallView: ...

    def stop(self, *, controller_id: str) -> ManagedControllerInstallView: ...

    def restart(self, *, controller_id: str) -> ManagedControllerInstallView: ...

    def status(self, *, controller_id: str) -> ManagedControllerStatusView: ...
