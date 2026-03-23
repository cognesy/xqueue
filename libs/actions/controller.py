"""Controller supervision actions."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from libs.actions.logging import log_action
from libs.domain.config import EffectiveConfig
from libs.domain.models import ControllerState
from libs.domain.responses import DetailResponse, MutationResponse
from libs.services.controller import ControllerService


class RunControllerAction:
    """Run the controller supervision loop in direct mode."""

    def __init__(self, controller_service: ControllerService) -> None:
        self._controller_service = controller_service

    @log_action(
        "run_controller",
        context_getter=lambda self, *, controller_id, config, workspace_root, use_workspace_instance, max_supervision_loops=None, reload_config=None: {
            "controller_id": controller_id,
            "pool_count": len(config.controller.pools),
            "workspace_root": str(workspace_root),
            "use_workspace_instance": use_workspace_instance,
            "max_supervision_loops": max_supervision_loops,
        },
        result_getter=lambda result: {"controller_id": result.item.controller_id, "state": result.item.state.value},
    )
    def __call__(
        self,
        *,
        controller_id: str,
        config,
        reload_config: Callable[[], EffectiveConfig] | None = None,
        workspace_root: Path,
        use_workspace_instance: bool,
        max_supervision_loops: int | None = None,
    ) -> DetailResponse:
        item = self._controller_service.run(
            controller_id=controller_id,
            config=config,
            reload_config=reload_config,
            workspace_root=workspace_root,
            use_workspace_instance=use_workspace_instance,
            max_supervision_loops=max_supervision_loops,
        )
        return DetailResponse(item=item)


class ShowControllerStatusAction:
    """Return the current controller status snapshot."""

    def __init__(self, controller_service: ControllerService) -> None:
        self._controller_service = controller_service

    @log_action(
        "show_controller_status",
        context_getter=lambda self, *, controller_id: {"controller_id": controller_id},
        result_getter=lambda result: {"controller_id": result.item.controller_id, "state": result.item.state.value},
    )
    def __call__(self, *, controller_id: str, config) -> DetailResponse:
        return DetailResponse(item=self._controller_service.get_status(controller_id=controller_id, config=config))


class RequestControllerStateAction:
    """Persist a controller control request for the running controller loop."""

    def __init__(self, controller_service: ControllerService) -> None:
        self._controller_service = controller_service

    @log_action(
        "request_controller_state",
        context_getter=lambda self, *, controller_id, requested_state, runtime_root: {
            "controller_id": controller_id,
            "requested_state": requested_state.value,
            "runtime_root": str(runtime_root),
        },
        result_getter=lambda result: {
            "controller_id": result.item.controller_id,
            "requested_state": result.item.requested_state.value,
        },
    )
    def __call__(self, *, controller_id: str, runtime_root: Path, requested_state: ControllerState) -> MutationResponse:
        item = self._controller_service.request_state(
            controller_id=controller_id,
            runtime_root=runtime_root,
            requested_state=requested_state,
        )
        return MutationResponse(item=item)


class InstallManagedControllerAction:
    """Install a managed platform service for the controller."""

    def __init__(self, managed_service) -> None:
        self._managed_service = managed_service

    @log_action(
        "install_managed_controller",
        context_getter=lambda self, *, controller_id: {"controller_id": controller_id},
        result_getter=lambda result: {
            "controller_id": result.item.controller_id,
            "manager": result.item.manager.value,
            "action": result.item.action,
        },
    )
    def __call__(self, *, controller_id: str, workspace_root: Path, config, use_workspace_instance: bool) -> MutationResponse:
        item = self._managed_service.install(
            controller_id=controller_id,
            workspace_root=workspace_root,
            config_path=config.paths.config_file,
            log_root=config.paths.log_root,
            use_workspace_instance=use_workspace_instance,
        )
        return MutationResponse(item=item)


class UninstallManagedControllerAction:
    """Uninstall a managed platform service for the controller."""

    def __init__(self, managed_service) -> None:
        self._managed_service = managed_service

    @log_action(
        "uninstall_managed_controller",
        context_getter=lambda self, *, controller_id: {"controller_id": controller_id},
        result_getter=lambda result: {
            "controller_id": result.item.controller_id,
            "manager": result.item.manager.value,
            "action": result.item.action,
        },
    )
    def __call__(self, *, controller_id: str) -> MutationResponse:
        return MutationResponse(item=self._managed_service.uninstall(controller_id=controller_id))


class ManagedControllerLifecycleAction:
    """Run one managed controller lifecycle operation."""

    def __init__(self, managed_service, *, operation: str) -> None:
        self._managed_service = managed_service
        self._operation = operation

    @log_action(
        "managed_controller_lifecycle",
        context_getter=lambda self, *, controller_id: {"controller_id": controller_id, "operation": self._operation},
        result_getter=lambda result: {
            "controller_id": result.item.controller_id,
            "manager": result.item.manager.value,
            "action": result.item.action,
        },
    )
    def __call__(self, *, controller_id: str) -> MutationResponse:
        method = getattr(self._managed_service, self._operation)
        return MutationResponse(item=method(controller_id=controller_id))


class ManagedControllerStatusAction:
    """Inspect managed controller lifecycle state from the platform service manager."""

    def __init__(self, managed_service) -> None:
        self._managed_service = managed_service

    @log_action(
        "managed_controller_status",
        context_getter=lambda self, *, controller_id: {"controller_id": controller_id},
        result_getter=lambda result: {
            "controller_id": result.item.controller_id,
            "manager": result.item.manager.value,
            "installed": result.item.installed,
            "active": result.item.active,
        },
    )
    def __call__(self, *, controller_id: str) -> DetailResponse:
        return DetailResponse(item=self._managed_service.status(controller_id=controller_id))
