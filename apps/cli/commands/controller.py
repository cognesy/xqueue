"""Controller supervision CLI commands."""

from __future__ import annotations

from pathlib import Path
import sys

import typer

from apps.cli.output import Output, OutputFormat
from apps.cli.runtime import run_action
from libs.actions.controller import (
    EnsureControllerPoolAction,
    InstallManagedControllerAction,
    ListControllerPoolsAction,
    ManagedControllerLifecycleAction,
    ManagedControllerStatusAction,
    RemoveControllerPoolAction,
    RequestControllerStateAction,
    RunControllerAction,
    ShowControllerStatusAction,
    UninstallManagedControllerAction,
)
from libs.domain.config import RestartPolicy
from libs.domain.errors import ValidationError
from libs.domain.models import ControllerState, ServiceManagerKind
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.services.config import ConfigLoader, ControllerPoolConfigService
from libs.services.controller import ControllerService
from libs.services.database import SessionManager
from libs.services.launchd import LaunchdService
from libs.services.systemd import SystemdUserService
from libs.services.workers import WorkerService


app = typer.Typer(help="Supervise configured worker pools in direct controller mode.")
pools_app = typer.Typer(help="Manage static controller worker pool configuration.")


def _build_runtime(use_workspace_instance: bool):
    workspace_root = Path.cwd()
    config = ConfigLoader().load(
        workspace_root=workspace_root,
        use_workspace_instance=use_workspace_instance,
    )
    engine = create_sqlite_engine(config.paths.database_path)
    session_factory = create_session_factory(engine)
    controller_service = ControllerService(
        SessionManager(session_factory),
        WorkerService(),
    )
    return workspace_root, config, controller_service


def _resolve_config_path(use_workspace_instance: bool) -> Path:
    return ConfigLoader().resolve_paths(
        workspace_root=Path.cwd(),
        use_workspace_instance=use_workspace_instance,
    ).config_file


def _resolve_managed_platform(platform: ServiceManagerKind | None) -> ServiceManagerKind:
    if platform is not None:
        return platform
    if sys.platform == "darwin":
        return ServiceManagerKind.LAUNCHD
    if sys.platform.startswith("linux"):
        return ServiceManagerKind.SYSTEMD
    raise ValidationError("no supported managed controller platform for this system", details={"platform": sys.platform})


def _build_managed_service(platform: ServiceManagerKind | None):
    resolved = _resolve_managed_platform(platform)
    if resolved is ServiceManagerKind.LAUNCHD:
        return LaunchdService(python_executable=sys.executable)
    if resolved is ServiceManagerKind.SYSTEMD:
        return SystemdUserService(python_executable=sys.executable)
    raise ValidationError("unsupported managed controller platform", details={"platform": resolved.value})


@app.command("run")
def run_controller(
    ctx: typer.Context,
    controller_id: str = typer.Option("default", "--controller-id"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    max_supervision_loops: int | None = typer.Option(None, "--max-supervision-loops", min=1, hidden=True),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Run the controller loop directly from the shell."""
    workspace_root, config, controller_service = _build_runtime(use_workspace_instance)
    config_loader = ConfigLoader()
    action = RunControllerAction(controller_service)
    out = Output(ctx, "controller.run", output)
    run_action(
        lambda: action(
            controller_id=controller_id,
            config=config,
            reload_config=lambda: config_loader.load(
                workspace_root=workspace_root,
                use_workspace_instance=use_workspace_instance,
            ),
            workspace_root=workspace_root,
            use_workspace_instance=use_workspace_instance,
            max_supervision_loops=max_supervision_loops,
        ),
        out=out,
    )


@app.command("status")
def controller_status(
    ctx: typer.Context,
    controller_id: str = typer.Option("default", "--controller-id"),
    platform: ServiceManagerKind | None = typer.Option(None, "--platform"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Show the current controller status snapshot."""
    workspace_root, config, controller_service = _build_runtime(use_workspace_instance)
    out = Output(ctx, "controller.status", output)
    if platform is not None:
        managed_service = _build_managed_service(platform)
        action = ManagedControllerStatusAction(managed_service)
        run_action(lambda: action(controller_id=controller_id), out=out)
        return

    action = ShowControllerStatusAction(controller_service)
    run_action(lambda: action(controller_id=controller_id, config=config), out=out)


@app.command("install")
def install_controller(
    ctx: typer.Context,
    controller_id: str = typer.Option("default", "--controller-id"),
    platform: ServiceManagerKind | None = typer.Option(None, "--platform"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Install the managed controller service for the current platform."""
    workspace_root, config, _ = _build_runtime(use_workspace_instance)
    action = InstallManagedControllerAction(_build_managed_service(platform))
    out = Output(ctx, "controller.install", output)
    run_action(
        lambda: action(
            controller_id=controller_id,
            workspace_root=workspace_root,
            config=config,
            use_workspace_instance=use_workspace_instance,
        ),
        out=out,
    )


@app.command("uninstall")
def uninstall_controller(
    ctx: typer.Context,
    controller_id: str = typer.Option("default", "--controller-id"),
    platform: ServiceManagerKind | None = typer.Option(None, "--platform"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Uninstall the managed controller service for the current platform."""
    _build_runtime(use_workspace_instance)
    action = UninstallManagedControllerAction(_build_managed_service(platform))
    run_action(lambda: action(controller_id=controller_id), out=Output(ctx, "controller.uninstall", output))


@app.command("start")
def start_controller(
    ctx: typer.Context,
    controller_id: str = typer.Option("default", "--controller-id"),
    platform: ServiceManagerKind | None = typer.Option(None, "--platform"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Start the managed controller service for the current platform."""
    _build_runtime(use_workspace_instance)
    action = ManagedControllerLifecycleAction(_build_managed_service(platform), operation="start")
    run_action(lambda: action(controller_id=controller_id), out=Output(ctx, "controller.start", output))


def _request_state_command(requested_state: ControllerState):
    contract_name = {
        ControllerState.DRAINING: "controller.drain",
        ControllerState.RESTARTING: "controller.restart",
        ControllerState.STOPPING: "controller.stop",
    }[requested_state]

    def command(
        ctx: typer.Context,
        controller_id: str = typer.Option("default", "--controller-id"),
        platform: ServiceManagerKind | None = typer.Option(None, "--platform"),
        output: OutputFormat | None = typer.Option(None, "--output", "-o"),
        use_workspace_instance: bool = typer.Option(
            False,
            "--workspace-instance",
            help="Resolve runtime paths relative to the repository instance directory.",
            hidden=True,
        ),
    ) -> None:
        """Request a controller state change."""
        _, config, controller_service = _build_runtime(use_workspace_instance)
        out = Output(ctx, contract_name, output)
        if platform is not None:
            operation = "restart" if requested_state is ControllerState.RESTARTING else "stop"
            action = ManagedControllerLifecycleAction(_build_managed_service(platform), operation=operation)
            run_action(lambda: action(controller_id=controller_id), out=out)
            return

        action = RequestControllerStateAction(controller_service)
        run_action(
            lambda: action(
                controller_id=controller_id,
                runtime_root=config.paths.runtime_root,
                requested_state=requested_state,
            ),
            out=out,
        )

    return command


def _request_direct_state_command(requested_state: ControllerState):
    contract_name = {
        ControllerState.PAUSED: "controller.pause-intake",
        ControllerState.ACTIVE: "controller.resume-intake",
    }[requested_state]

    def command(
        ctx: typer.Context,
        controller_id: str = typer.Option("default", "--controller-id"),
        output: OutputFormat | None = typer.Option(None, "--output", "-o"),
        use_workspace_instance: bool = typer.Option(
            False,
            "--workspace-instance",
            help="Resolve runtime paths relative to the repository instance directory.",
            hidden=True,
        ),
    ) -> None:
        """Request a direct-mode controller state change."""
        _, config, controller_service = _build_runtime(use_workspace_instance)
        action = RequestControllerStateAction(controller_service)
        out = Output(ctx, contract_name, output)
        run_action(
            lambda: action(
                controller_id=controller_id,
                runtime_root=config.paths.runtime_root,
                requested_state=requested_state,
            ),
            out=out,
        )

    return command


app.command("pause-intake")(_request_direct_state_command(ControllerState.PAUSED))
app.command("resume-intake")(_request_direct_state_command(ControllerState.ACTIVE))
app.command("drain")(_request_state_command(ControllerState.DRAINING))
app.command("restart")(_request_state_command(ControllerState.RESTARTING))
app.command("stop")(_request_state_command(ControllerState.STOPPING))


@pools_app.command("list")
def list_controller_pools(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """List configured controller worker pools."""
    config_path = _resolve_config_path(use_workspace_instance)
    action = ListControllerPoolsAction(ControllerPoolConfigService())
    run_action(lambda: action(config_path=config_path), out=Output(ctx, "controller.pools.list", output))


@pools_app.command("ensure")
def ensure_controller_pool(
    ctx: typer.Context,
    name: str = typer.Argument(...),
    queue: list[str] = typer.Option(..., "--queue", "-q", help="Queue served by the pool. Repeat for multiple queues."),
    concurrency: int = typer.Option(1, "--concurrency", min=1),
    poll_interval_seconds: float | None = typer.Option(None, "--poll-interval", min=0.001),
    lease_seconds: int = typer.Option(30, "--lease", min=1),
    restart_policy: RestartPolicy = typer.Option(RestartPolicy.ON_FAILURE, "--restart-policy"),
    default_timeout_seconds: int | None = typer.Option(None, "--timeout", min=1),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Create or update a configured controller worker pool."""
    config_path = _resolve_config_path(use_workspace_instance)
    action = EnsureControllerPoolAction(ControllerPoolConfigService())
    run_action(
        lambda: action(
            config_path=config_path,
            name=name,
            queues=queue,
            concurrency=concurrency,
            poll_interval_seconds=poll_interval_seconds,
            lease_seconds=lease_seconds,
            restart_policy=restart_policy,
            default_timeout_seconds=default_timeout_seconds,
        ),
        out=Output(ctx, "controller.pools.ensure", output),
    )


@pools_app.command("remove")
def remove_controller_pool(
    ctx: typer.Context,
    name: str = typer.Argument(...),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Remove a configured controller worker pool."""
    config_path = _resolve_config_path(use_workspace_instance)
    action = RemoveControllerPoolAction(ControllerPoolConfigService())
    run_action(lambda: action(config_path=config_path, name=name), out=Output(ctx, "controller.pools.remove", output))


app.add_typer(pools_app, name="pools")
