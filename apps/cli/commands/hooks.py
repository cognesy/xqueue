"""Hooks CLI commands for Claude Code and Codex integration."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

import typer
from xqueue.workspace.models import HookInstallItem, HookStatusItem
from xqueue_cli.client import open_client
from xqueue_cli.contracts import DetailResponse, MutationResponse
from xqueue_cli.home import build_home_response, collapse_home_path
from xqueue_cli.output import Output, OutputFormat

app = typer.Typer(help="Manage agent session hooks for Claude Code and Codex.")

ItemT = TypeVar("ItemT", HookInstallItem, HookStatusItem)


def _for_display(item: ItemT) -> ItemT:
    """Collapse the home directory at the channel edge; the facet returns real paths."""
    return item.model_copy(update={"executable_path": collapse_home_path(item.executable_path)})


@app.command("install")
def hooks_install(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Install or update repo-local session hooks."""
    out = Output(ctx, "hooks.install", output)
    with open_client() as client:
        out.print(MutationResponse(item=_for_display(client.workspace.install_hooks())))


@app.command("status")
def hooks_status(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Inspect repo-local hook installation state."""
    out = Output(ctx, "hooks.status", output)
    with open_client() as client:
        out.print(DetailResponse(item=_for_display(client.workspace.hook_status())))


@app.command("session-start", hidden=True)
def hooks_session_start(ctx: typer.Context) -> None:
    """Output the compact home dashboard for session-start hooks."""
    out = Output(ctx, "home", OutputFormat.TOON)
    out.print(build_home_response(Path.cwd()))


@app.command("session-end", hidden=True)
def hooks_session_end(ctx: typer.Context) -> None:
    """Capture session metadata for future hooks."""
    out = Output(ctx, "hooks.session-end", OutputFormat.TOON)
    with open_client() as client:
        out.print(MutationResponse(item=client.workspace.capture_session_end()))
