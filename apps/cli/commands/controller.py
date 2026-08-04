"""Controller supervision CLI commands."""

from __future__ import annotations

from collections.abc import Callable

import typer
from xqueue.controller.models import ControllerState, ServiceManagerKind
from xqueue.workspace.models import RestartPolicy
from xqueue_cli.client import open_client
from xqueue_cli.contracts import DetailResponse, ListResponse, MutationResponse
from xqueue_cli.controller_pools import for_display
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action

app = typer.Typer(help="Supervise configured worker pools in direct controller mode.")
pools_app = typer.Typer(help="Manage static controller worker pool configuration.")


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
    out = Output(ctx, "controller.run", output)
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(
            lambda: DetailResponse(
                item=xq.controller.run(
                    controller_id=controller_id,
                    max_supervision_loops=max_supervision_loops,
                )
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
    out = Output(ctx, "controller.status", output)
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(
            lambda: DetailResponse(item=xq.controller.status(controller_id=controller_id, platform=platform)),
            out=out,
        )


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
    out = Output(ctx, "controller.install", output)
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(
            lambda: MutationResponse(item=xq.controller.install(controller_id=controller_id, platform=platform)),
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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(
            lambda: MutationResponse(item=xq.controller.uninstall(controller_id=controller_id, platform=platform)),
            out=Output(ctx, "controller.uninstall", output),
        )


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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(
            lambda: MutationResponse(
                item=xq.controller.managed_lifecycle(
                    controller_id=controller_id,
                    operation="start",
                    platform=platform,
                )
            ),
            out=Output(ctx, "controller.start", output),
        )


def _request_state_command(requested_state: ControllerState) -> Callable[..., None]:
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
        out = Output(ctx, contract_name, output)
        with open_client(use_workspace_instance=use_workspace_instance) as xq:
            if platform is not None:
                operation = "restart" if requested_state is ControllerState.RESTARTING else "stop"
                run_action(
                    lambda: MutationResponse(
                        item=xq.controller.managed_lifecycle(
                            controller_id=controller_id,
                            operation=operation,
                            platform=platform,
                        )
                    ),
                    out=out,
                )
                return
            run_action(
                lambda: MutationResponse(
                    item=xq.controller.request_state(
                        controller_id=controller_id,
                        requested_state=requested_state,
                    )
                ),
                out=out,
            )

    return command


def _request_direct_state_command(requested_state: ControllerState) -> Callable[..., None]:
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
        out = Output(ctx, contract_name, output)
        with open_client(use_workspace_instance=use_workspace_instance) as xq:
            run_action(
                lambda: MutationResponse(
                    item=xq.controller.request_state(
                        controller_id=controller_id,
                        requested_state=requested_state,
                    )
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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(
            lambda: ListResponse(items=xq.controller.list_pools()),
            out=Output(ctx, "controller.pools.list", output),
        )


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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(
            lambda: MutationResponse(
                item=for_display(
                    xq.controller.ensure_pool(
                        name=name,
                        queues=queue,
                        concurrency=concurrency,
                        poll_interval_seconds=poll_interval_seconds,
                        lease_seconds=lease_seconds,
                        restart_policy=restart_policy,
                        default_timeout_seconds=default_timeout_seconds,
                    )
                )
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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(
            lambda: MutationResponse(item=for_display(xq.controller.remove_pool(name=name))),
            out=Output(ctx, "controller.pools.remove", output),
        )


app.add_typer(pools_app, name="pools")
