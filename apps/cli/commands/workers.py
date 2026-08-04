"""Worker inspection and control CLI commands."""

from __future__ import annotations

from collections.abc import Callable

import typer
from xqueue.workers.models import WorkerState
from xqueue_cli.client import open_client
from xqueue_cli.contracts import ListResponse, MutationResponse
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action

app = typer.Typer(help="Inspect and control persisted worker state.")


@app.command("list")
def list_workers(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """List workers with queues, heartbeat, and operational state."""
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(lambda: ListResponse(items=xq.workers.list()), out=Output(ctx, "workers.list", output))


def _set_state_command(state: WorkerState) -> Callable[..., None]:
    contract_name = {
        WorkerState.PAUSED: "workers.pause",
        WorkerState.ACTIVE: "workers.resume",
        WorkerState.DRAINING: "workers.drain",
        WorkerState.STOPPED: "workers.stop",
    }[state]

    def command(
        ctx: typer.Context,
        worker_id: str = typer.Argument(..., metavar="WORKER_ID"),
        output: OutputFormat | None = typer.Option(None, "--output", "-o"),
        use_workspace_instance: bool = typer.Option(
            False,
            "--workspace-instance",
            help="Resolve runtime paths relative to the repository instance directory.",
            hidden=True,
        ),
    ) -> None:
        """Persist a worker state change."""
        with open_client(use_workspace_instance=use_workspace_instance) as xq:
            run_action(
                lambda: MutationResponse(item=xq.workers.set_state(worker_id, state)),
                out=Output(ctx, contract_name, output),
            )

    return command


app.command("pause")(_set_state_command(WorkerState.PAUSED))
app.command("resume")(_set_state_command(WorkerState.ACTIVE))
app.command("drain")(_set_state_command(WorkerState.DRAINING))
app.command("stop")(_set_state_command(WorkerState.STOPPED))
