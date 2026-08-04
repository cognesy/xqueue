"""Public SDK facet for controller operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xqueue.controller.actions import (
    InstallManagedControllerAction,
    ManagedControllerLifecycleAction,
    ManagedControllerStatusAction,
    UninstallManagedControllerAction,
)
from xqueue.controller.models import (
    ControllerCommandResult,
    ControllerPoolConfigView,
    ControllerPoolMutationResult,
    ControllerState,
    ControllerStatusView,
    ManagedControllerInstallView,
    ManagedControllerStatusView,
    ServiceManagerKind,
)
from xqueue.workspace.models import RestartPolicy

if TYPE_CHECKING:
    from xqueue.runtime.composition import Runtime


class Controller:
    """Typed direct and managed controller operations over one runtime."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def run(self, *, controller_id: str = "default", max_supervision_loops: int | None = None) -> ControllerStatusView:
        self._runtime.ensure_open()
        return self._runtime.controller_actions.run(
            controller_id=controller_id,
            config=self._runtime.config,
            reload_config=self._runtime.reload_config,
            workspace_root=self._runtime.workspace_root,
            use_workspace_instance=self._runtime.use_workspace_instance,
            max_supervision_loops=max_supervision_loops,
        )

    def status(
        self,
        *,
        controller_id: str = "default",
        platform: ServiceManagerKind | None = None,
    ) -> ControllerStatusView | ManagedControllerStatusView:
        self._runtime.ensure_open()
        if platform is None:
            return self._runtime.controller_actions.status(controller_id=controller_id, config=self._runtime.config)
        return ManagedControllerStatusAction(self._runtime.managed_controller_service(platform))(
            controller_id=controller_id
        )

    def request_state(self, *, controller_id: str, requested_state: ControllerState) -> ControllerCommandResult:
        self._runtime.ensure_open()
        return self._runtime.controller_actions.request_state(
            controller_id=controller_id,
            runtime_root=self._runtime.config.paths.runtime_root,
            requested_state=requested_state,
        )

    def install(
        self,
        *,
        controller_id: str = "default",
        platform: ServiceManagerKind | None = None,
    ) -> ManagedControllerInstallView:
        self._runtime.ensure_open()
        return InstallManagedControllerAction(self._runtime.managed_controller_service(platform))(
            controller_id=controller_id,
            workspace_root=self._runtime.workspace_root,
            config=self._runtime.config,
            use_workspace_instance=self._runtime.use_workspace_instance,
        )

    def uninstall(
        self,
        *,
        controller_id: str = "default",
        platform: ServiceManagerKind | None = None,
    ) -> ManagedControllerInstallView:
        self._runtime.ensure_open()
        return UninstallManagedControllerAction(self._runtime.managed_controller_service(platform))(
            controller_id=controller_id
        )

    def managed_lifecycle(
        self,
        *,
        controller_id: str,
        operation: str,
        platform: ServiceManagerKind | None = None,
    ) -> ManagedControllerInstallView:
        self._runtime.ensure_open()
        return ManagedControllerLifecycleAction(
            self._runtime.managed_controller_service(platform), operation=operation
        )(controller_id=controller_id)

    def list_pools(self) -> list[ControllerPoolConfigView]:
        self._runtime.ensure_open()
        return self._runtime.controller_actions.list_pools(config_path=self._runtime.config.paths.config_file)

    def ensure_pool(
        self,
        *,
        name: str,
        queues: list[str],
        concurrency: int,
        poll_interval_seconds: float | None = None,
        lease_seconds: int = 30,
        restart_policy: RestartPolicy = RestartPolicy.ON_FAILURE,
        default_timeout_seconds: int | None = None,
    ) -> ControllerPoolMutationResult:
        self._runtime.ensure_open()
        result = self._runtime.controller_actions.ensure_pool(
            config_path=self._runtime.config.paths.config_file,
            name=name,
            queues=queues,
            concurrency=concurrency,
            poll_interval_seconds=poll_interval_seconds,
            lease_seconds=lease_seconds,
            restart_policy=restart_policy,
            default_timeout_seconds=default_timeout_seconds,
        )
        self._runtime.reload_config()
        return result

    def remove_pool(self, *, name: str) -> ControllerPoolMutationResult:
        self._runtime.ensure_open()
        result = self._runtime.controller_actions.remove_pool(
            config_path=self._runtime.config.paths.config_file,
            name=name,
        )
        self._runtime.reload_config()
        return result
