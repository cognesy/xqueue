"""Configuration-related CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from xqueue_cli.client import open_client
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action

app = typer.Typer(help="Inspect static configuration and resolved runtime paths.")


@app.command("show")
def show_config(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    config_path: Path | None = typer.Option(None, "--config-path"),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        help="Use the workspace at this root instead of discovering one.",
    ),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Deprecated alias for `--workspace .`.",
    ),
) -> None:
    """Show the effective xqueue configuration."""
    out = Output(ctx, "config.show", output)

    with open_client(
        config_path=config_path,
        workspace_root=workspace,
        use_workspace_instance=use_workspace_instance or workspace is not None,
    ) as client:
        run_action(
            client.workspace.config,
            out=out,
        )
