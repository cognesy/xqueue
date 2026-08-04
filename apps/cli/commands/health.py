"""Top-level health command."""

from __future__ import annotations

import typer
from xqueue_cli.client import open_client
from xqueue_cli.contracts import DetailResponse
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action


def register(app: typer.Typer) -> None:
    @app.command("health")
    def health(
        ctx: typer.Context,
        output: OutputFormat | None = typer.Option(None, "--output", "-o"),
        use_workspace_instance: bool = typer.Option(
            False,
            "--workspace-instance",
            help="Resolve runtime paths relative to the repository instance directory.",
            hidden=True,
        ),
    ) -> None:
        """Summarize database, queue, worker, and lease health."""
        with open_client(use_workspace_instance=use_workspace_instance) as client:
            run_action(
                lambda: DetailResponse(item=client.maintenance.health()),
                out=Output(ctx, "health", output),
            )
