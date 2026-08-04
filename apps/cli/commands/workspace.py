"""Workspace management commands."""

from __future__ import annotations

from pathlib import Path

import typer
from xqueue_cli.client import open_client
from xqueue_cli.contracts import MutationResponse
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action

app = typer.Typer(help="Create and inspect the workspace this directory belongs to.")


@app.command("init")
def init(
    ctx: typer.Context,
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Workspace root to initialize. Defaults to the current directory.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Rewrite config.yaml. Other files are never removed.",
    ),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Create `.xqueue/` here, or complete a partial one."""
    out = Output(ctx, "workspace.init", output)
    with open_client(workspace_root=root or Path.cwd(), use_workspace_instance=True) as xq:
        run_action(
            lambda: MutationResponse(item=xq.workspace.init(force=force)),
            out=out,
        )
