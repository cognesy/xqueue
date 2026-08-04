"""Database maintenance CLI commands."""

from __future__ import annotations

import typer
from xqueue.core.errors import ValidationError
from xqueue_cli.client import open_client
from xqueue_cli.contracts import DetailResponse, MutationResponse
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action

app = typer.Typer(help="Inspect and maintain the SQLite state store.")


@app.command("check")
def check_database(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Run SQLite integrity and schema checks."""

    def execute() -> DetailResponse:
        with open_client(use_workspace_instance=use_workspace_instance) as client:
            return DetailResponse(item=client.maintenance.check_database())

    run_action(execute, out=Output(ctx, "db.check", output))


@app.command("vacuum")
def vacuum_database(
    ctx: typer.Context,
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Run SQLite VACUUM."""

    def execute() -> MutationResponse:
        with open_client(use_workspace_instance=use_workspace_instance) as client:
            return MutationResponse(item=client.maintenance.vacuum_database())

    run_action(execute, out=Output(ctx, "db.vacuum", output))


@app.command("reset-workspace-instance")
def reset_workspace_instance(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", help="Confirm removal of repo-local instance runtime artifacts."),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Reset repo-local instance DB, runtime, and log artifacts for manual verification."""

    def execute() -> object:
        if not yes:
            raise ValidationError("reset-workspace-instance requires --yes confirmation")
        with open_client(use_workspace_instance=True) as client:
            return MutationResponse(item=client.workspace.reset_instance())

    run_action(execute, out=Output(ctx, "db.reset-workspace-instance", output))


@app.command("cleanup-retention")
def cleanup_retention(
    ctx: typer.Context,
    older_than_hours: int = typer.Option(..., "--older-than-hours", min=1),
    yes: bool = typer.Option(False, "--yes", help="Confirm destructive retention cleanup."),
    prune_attempts: bool = typer.Option(True, "--attempts/--no-attempts"),
    prune_events: bool = typer.Option(True, "--events/--no-events"),
    prune_logs: bool = typer.Option(True, "--logs/--no-logs"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Prune old attempts, events, and logs explicitly."""

    def execute() -> object:
        if not yes:
            raise ValidationError("cleanup-retention requires --yes confirmation")
        with open_client(use_workspace_instance=use_workspace_instance) as client:
            return MutationResponse(
                item=client.maintenance.cleanup_retention(
                    older_than_hours=older_than_hours,
                    prune_attempts=prune_attempts,
                    prune_events=prune_events,
                    prune_logs=prune_logs,
                )
            )

    run_action(execute, out=Output(ctx, "db.cleanup-retention", output))
