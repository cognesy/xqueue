"""Runtime metrics commands."""

from __future__ import annotations

import typer

from apps.cli.output import Output, OutputFormat
from apps.cli.runtime import run_action
from libs.actions.metrics import ResetMetricsAction, ShowMetricsAction

app = typer.Typer(help="Inspect and reset persisted runtime metrics.")


@app.command("show")
def show_metrics(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Show persisted xqueue runtime metrics."""
    run_action(ShowMetricsAction(), out=Output(ctx, "metrics.show", output))


@app.command("reset")
def reset_metrics(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Reset persisted xqueue runtime metrics."""
    run_action(ResetMetricsAction(), out=Output(ctx, "metrics.reset", output))
