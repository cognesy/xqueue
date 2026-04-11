"""Configuration-related CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from apps.cli.output import Output, OutputFormat
from apps.cli.runtime import run_action
from libs.actions.config import ShowConfigAction
from libs.services.config import ConfigLoader


app = typer.Typer(help="Inspect static configuration and resolved runtime paths.")


@app.command("show")
def show_config(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    config_path: Path | None = typer.Option(None, "--config-path"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve paths relative to the repository instance directory.",
    ),
) -> None:
    """Show the effective xqueue configuration."""
    action = ShowConfigAction(ConfigLoader())
    out = Output(ctx, "config.show", output)

    run_action(
        lambda: action(
            config_path=config_path,
            workspace_root=Path.cwd(),
            use_workspace_instance=use_workspace_instance,
        ),
        out=out,
    )
