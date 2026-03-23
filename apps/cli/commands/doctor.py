"""Top-level doctor command."""

from __future__ import annotations

from pathlib import Path

import typer

from apps.cli.output import OutputFormat
from apps.cli.runtime import run_action
from libs.actions.operations import DoctorAction
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.services.config import ConfigLoader
from libs.services.database import SessionManager
from libs.services.database_maintenance import DatabaseMaintenanceService
from libs.services.health import HealthService


def register(app: typer.Typer) -> None:
    @app.command("doctor")
    def doctor(
        output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
        use_workspace_instance: bool = typer.Option(
            False,
            "--workspace-instance",
            help="Resolve runtime paths relative to the repository instance directory.",
            hidden=True,
        ),
    ) -> None:
        """Run detailed operational diagnostics."""
        config = ConfigLoader().load(
            workspace_root=Path.cwd(),
            use_workspace_instance=use_workspace_instance,
        )
        engine = create_sqlite_engine(config.paths.database_path)
        session_factory = create_session_factory(engine)
        action = DoctorAction(
            SessionManager(session_factory),
            HealthService(),
            DatabaseMaintenanceService(engine, database_path=config.paths.database_path),
        )
        run_action(action, output_format=output)
