"""Database maintenance CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from apps.cli.output import Output, OutputFormat
from apps.cli.runtime import run_action
from libs.actions.operations import CheckDatabaseAction, CleanupRetentionAction, ResetWorkspaceInstanceAction, VacuumDatabaseAction
from libs.domain.errors import ValidationError
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.services.config import ConfigLoader
from libs.services.database import SessionManager
from libs.services.database_maintenance import DatabaseMaintenanceService
from libs.services.job_logs import JobLogService
from libs.services.retention import RetentionCleanupService
from libs.services.workspace_instance import WorkspaceInstanceService


app = typer.Typer(help="Inspect and maintain the SQLite state store.")
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _build_database_service(use_workspace_instance: bool) -> DatabaseMaintenanceService:
    config = ConfigLoader().load(
        workspace_root=Path.cwd(),
        use_workspace_instance=use_workspace_instance,
    )
    engine = create_sqlite_engine(config.paths.database_path)
    return DatabaseMaintenanceService(engine, database_path=config.paths.database_path)


def _build_session_manager(use_workspace_instance: bool) -> SessionManager:
    config = ConfigLoader().load(
        workspace_root=Path.cwd(),
        use_workspace_instance=use_workspace_instance,
    )
    engine = create_sqlite_engine(config.paths.database_path)
    session_factory = create_session_factory(engine)
    return SessionManager(session_factory)


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
    action = CheckDatabaseAction(_build_database_service(use_workspace_instance))
    run_action(action, out=Output(ctx, "db.check", output))


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
    action = VacuumDatabaseAction(_build_database_service(use_workspace_instance))
    run_action(action, out=Output(ctx, "db.vacuum", output))


@app.command("reset-workspace-instance")
def reset_workspace_instance(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", help="Confirm removal of repo-local instance runtime artifacts."),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Reset repo-local instance DB, runtime, and log artifacts for manual verification."""
    action = ResetWorkspaceInstanceAction(WorkspaceInstanceService())

    def execute() -> object:
        if not yes:
            raise ValidationError("reset-workspace-instance requires --yes confirmation")
        paths = ConfigLoader().resolve_paths(
            workspace_root=Path.cwd(),
            use_workspace_instance=True,
        )
        return action(paths, alembic_ini_path=_REPO_ROOT / "alembic.ini")

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
    action = CleanupRetentionAction(
        _build_session_manager(use_workspace_instance),
        RetentionCleanupService(),
        JobLogService(),
    )

    def execute() -> object:
        if not yes:
            raise ValidationError("cleanup-retention requires --yes confirmation")
        return action(
            older_than_hours=older_than_hours,
            prune_attempts=prune_attempts,
            prune_events=prune_events,
            prune_logs=prune_logs,
        )

    run_action(execute, out=Output(ctx, "db.cleanup-retention", output))
