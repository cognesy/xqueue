"""Hooks CLI commands for Claude Code and Codex integration."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import typer

from xqueue_cli.home import build_home_response, collapse_home_path
from xqueue_cli.output import Output, OutputFormat
from xqueue_libs.domain.responses import (
    ClaudeHookStatus,
    CodexHookStatus,
    DetailResponse,
    HookInstallItem,
    HookStatusItem,
    MutationResponse,
    SessionCaptureItem,
)
from xqueue_libs.services.session_hooks import capture_session_end, ensure_agent_hooks, inspect_agent_hooks


app = typer.Typer(help="Manage agent session hooks for Claude Code and Codex.")


@app.command("install")
def hooks_install(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Install or update repo-local session hooks."""
    out = Output(ctx, "hooks.install", output)
    result = ensure_agent_hooks(Path.cwd())
    out.print(
        MutationResponse(
            item=HookInstallItem(
                executable_path=collapse_home_path(result.executable_path),
                changed_files=list(result.changed_files),
            )
        )
    )


@app.command("status")
def hooks_status(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Inspect repo-local hook installation state."""
    out = Output(ctx, "hooks.status", output)
    result = inspect_agent_hooks(Path.cwd())
    out.print(
        DetailResponse(
            item=HookStatusItem(
                executable_path=collapse_home_path(result.executable_path),
                claude=ClaudeHookStatus(**asdict(result.claude)),
                codex=CodexHookStatus(**asdict(result.codex)),
            )
        )
    )


@app.command("session-start", hidden=True)
def hooks_session_start(ctx: typer.Context) -> None:
    """Output the compact home dashboard for session-start hooks."""
    out = Output(ctx, "home", OutputFormat.TOON)
    out.print(build_home_response(Path.cwd()))


@app.command("session-end", hidden=True)
def hooks_session_end(ctx: typer.Context) -> None:
    """Capture session metadata for future hooks."""
    out = Output(ctx, "hooks.session-end", OutputFormat.TOON)
    log_path = capture_session_end(Path.cwd())
    out.print(MutationResponse(item=SessionCaptureItem(log_path=str(log_path))))
