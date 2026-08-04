"""Queue inspection and control CLI commands."""

from __future__ import annotations

import typer
from xqueue_cli.client import open_client
from xqueue_cli.contracts import ListResponse, MutationResponse
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action

app = typer.Typer(help="Inspect and control queue state.")


@app.command("list")
def list_queues(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """List known queues and their current state."""
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(lambda: ListResponse(items=xq.queues.list()), out=Output(ctx, "queues.list", output))


@app.command("stats")
def queue_stats(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """List queue state and per-state job counts."""
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(lambda: ListResponse(items=xq.queues.stats()), out=Output(ctx, "queues.stats", output))


@app.command("pause")
def pause_queue(
    ctx: typer.Context,
    queue: str = typer.Argument(..., metavar="QUEUE"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Pause a queue so new claims stop."""
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(lambda: MutationResponse(item=xq.queues.pause(queue)), out=Output(ctx, "queues.pause", output))


@app.command("resume")
def resume_queue(
    ctx: typer.Context,
    queue: str = typer.Argument(..., metavar="QUEUE"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Resume a paused queue."""
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(lambda: MutationResponse(item=xq.queues.resume(queue)), out=Output(ctx, "queues.resume", output))
