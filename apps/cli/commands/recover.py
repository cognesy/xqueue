"""Recovery CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from apps.cli.output import OutputFormat
from apps.cli.runtime import run_action
from libs.actions.recovery import RecoverStaleLeasesAction
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.services.config import ConfigLoader
from libs.services.database import SessionManager
from libs.services.recovery import RecoveryService


app = typer.Typer(help="Recover stale worker leases and related runtime issues.")


@app.command("stale-leases")
def recover_stale_leases(
    retry_delay_seconds: int | None = typer.Option(None, "--retry-delay-seconds", min=0),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Recover expired running-job leases."""
    config = ConfigLoader().load(
        workspace_root=Path.cwd(),
        use_workspace_instance=use_workspace_instance,
    )
    engine = create_sqlite_engine(config.paths.database_path)
    session_factory = create_session_factory(engine)
    action = RecoverStaleLeasesAction(
        SessionManager(session_factory),
        RecoveryService(),
        retry_delay_seconds=config.worker.retry_delay_seconds if retry_delay_seconds is None else retry_delay_seconds,
    )
    run_action(action, output_format=output)
