"""Recovery CLI commands."""

from __future__ import annotations

import typer
from xqueue_cli.client import open_client
from xqueue_cli.contracts import MutationResponse
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action

app = typer.Typer(help="Recover stale worker leases and related runtime issues.")


@app.command("stale-leases")
def recover_stale_leases(
    ctx: typer.Context,
    retry_delay_seconds: int | None = typer.Option(None, "--retry-delay-seconds", min=0),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Recover expired running-job leases."""

    def execute() -> MutationResponse:
        with open_client(use_workspace_instance=use_workspace_instance) as client:
            return MutationResponse(
                item=client.maintenance.recover_stale_leases(retry_delay_seconds=retry_delay_seconds)
            )

    run_action(execute, out=Output(ctx, "recover.stale-leases", output))
