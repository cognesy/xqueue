"""Runtime metrics commands."""

from __future__ import annotations

import typer
from xqueue_cli.client import open_client
from xqueue_cli.contracts import DetailResponse, MutationResponse
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action

app = typer.Typer(help="Inspect and reset persisted runtime metrics.")


@app.command("show")
def show_metrics(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Show persisted xqueue runtime metrics."""

    def execute() -> DetailResponse:
        with open_client() as client:
            return DetailResponse(item=client.maintenance.metrics())

    run_action(execute, out=Output(ctx, "metrics.show", output))


@app.command("reset")
def reset_metrics(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Reset persisted xqueue runtime metrics."""

    def execute() -> MutationResponse:
        with open_client() as client:
            return MutationResponse(item=client.maintenance.reset_metrics())

    run_action(execute, out=Output(ctx, "metrics.reset", output))
