"""Workspace SDK facet."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from xqueue.workspace.hooks import capture_session_end, ensure_agent_hooks, inspect_agent_hooks
from xqueue.workspace.models import (
    ClaudeHookStatus,
    CodexHookStatus,
    EffectiveConfig,
    HookInstallItem,
    HookStatusItem,
    SessionCaptureItem,
    WorkspaceInitResult,
    WorkspaceInstanceResetResult,
)

if TYPE_CHECKING:
    from xqueue.runtime.composition import Runtime


class Workspace:
    """Read resolved workspace configuration."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def config(self) -> EffectiveConfig:
        return self._runtime.effective_config()

    def init(self, *, force: bool = False) -> WorkspaceInitResult:
        """Create or complete this client's workspace directory."""
        self._runtime.ensure_open()
        return self._runtime.initialize_workspace(force=force)

    def reset_instance(self) -> WorkspaceInstanceResetResult:
        self._runtime.ensure_open()
        return self._runtime.reset_workspace_instance(self._runtime.config.paths)

    def install_hooks(self) -> HookInstallItem:
        self._runtime.ensure_open()
        result = ensure_agent_hooks(self._runtime.workspace_root)
        return HookInstallItem(
            executable_path=result.executable_path,
            changed_files=list(result.changed_files),
        )

    def hook_status(self) -> HookStatusItem:
        self._runtime.ensure_open()
        result = inspect_agent_hooks(self._runtime.workspace_root)
        return HookStatusItem(
            executable_path=result.executable_path,
            claude=ClaudeHookStatus(**asdict(result.claude)),
            codex=CodexHookStatus(**asdict(result.codex)),
        )

    def capture_session_end(self) -> SessionCaptureItem:
        self._runtime.ensure_open()
        path = capture_session_end(self._runtime.workspace_root)
        return SessionCaptureItem(log_path=str(path))
