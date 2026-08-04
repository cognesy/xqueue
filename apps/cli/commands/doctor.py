"""Top-level doctor command."""

from __future__ import annotations

import typer
from xqueue_cli.client import open_client
from xqueue_cli.contracts import DetailResponse
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action


def register(app: typer.Typer) -> None:
    @app.command("doctor")
    def doctor(
        ctx: typer.Context,
        output: OutputFormat | None = typer.Option(None, "--output", "-o"),
        use_workspace_instance: bool = typer.Option(
            False,
            "--workspace-instance",
            help="Resolve runtime paths relative to the repository instance directory.",
            hidden=True,
        ),
    ) -> None:
        """Run detailed operational diagnostics."""

        def execute() -> DetailResponse:
            with open_client(use_workspace_instance=use_workspace_instance) as client:
                return DetailResponse(item=client.maintenance.doctor())

        run_action(execute, out=Output(ctx, "doctor", output))
