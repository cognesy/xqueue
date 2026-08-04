"""Actions related to resolved workspace configuration."""

from __future__ import annotations

from xqueue.runtime.action_logging import log_action
from xqueue.workspace.init import WorkspaceInitService
from xqueue.workspace.inputs import NO_CONFIG_INPUTS, ConfigInputs
from xqueue.workspace.instance import WorkspaceInstanceService
from xqueue.workspace.loader import SettingsLoader
from xqueue.workspace.models import (
    EffectiveConfig,
    RuntimePaths,
    WorkspaceInitResult,
    WorkspaceInstanceResetResult,
)
from xqueue.workspace.paths import Workspace


class ShowConfigAction:
    """Return the effective xqueue configuration."""

    def __init__(self, loader: SettingsLoader) -> None:
        self._loader = loader

    @log_action(
        "show_config",
        context_getter=lambda self, workspace, **kwargs: {
            "scope": str(workspace.scope),
            "has_config_path": kwargs.get("inputs", NO_CONFIG_INPUTS).config_path is not None,
            "env_name": kwargs.get("inputs", NO_CONFIG_INPUTS).env_name or "",
            "override_count": len(kwargs.get("inputs", NO_CONFIG_INPUTS).overrides),
        },
    )
    def __call__(
        self,
        workspace: Workspace,
        *,
        inputs: ConfigInputs = NO_CONFIG_INPUTS,
    ) -> EffectiveConfig:
        return self._loader.load(workspace, inputs=inputs)


class InitializeWorkspaceAction:
    """Create or complete a workspace, and say what changed."""

    def __init__(self, init_service: WorkspaceInitService) -> None:
        self._init_service = init_service

    @log_action(
        "initialize_workspace",
        context_getter=lambda self, workspace, **kwargs: {
            "directory": str(workspace.directory),
            "force": kwargs.get("force", False),
        },
        result_getter=lambda result: {
            "created_path_count": len(result.created_paths),
            "retained_path_count": len(result.retained_paths),
            "conflicting_path_count": len(result.conflicting_paths),
        },
    )
    def __call__(
        self,
        workspace: Workspace,
        *,
        created_by: str,
        force: bool = False,
    ) -> WorkspaceInitResult:
        return self._init_service.initialize(workspace, created_by=created_by, force=force)


class ResetWorkspaceInstanceAction:
    """Reset repo-local runtime artifacts under the owned instance tree."""

    def __init__(self, workspace_instance_service: WorkspaceInstanceService) -> None:
        self._workspace_instance_service = workspace_instance_service

    @log_action(
        "reset_workspace_instance",
        context_getter=lambda self, paths: {"state_root": str(paths.state_root)},
        result_getter=lambda result: {
            "state_root": result.state_root,
            "removed_path_count": len(result.removed_paths),
            "recreated_path_count": len(result.recreated_paths),
        },
    )
    def __call__(self, paths: RuntimePaths) -> WorkspaceInstanceResetResult:
        return self._workspace_instance_service.reset(paths=paths)
