"""Top-level doctor command."""

from __future__ import annotations

from pathlib import Path

import typer

from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action
from xqueue_libs.actions.operations import DoctorAction
from xqueue_libs.infra.database import create_session_factory, create_sqlite_engine
from xqueue_libs.services.config import ConfigLoader
from xqueue_libs.services.database import SessionManager
from xqueue_libs.services.database_maintenance import DatabaseMaintenanceService
from xqueue_libs.services.health import HealthService


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
        run_action(action, out=Output(ctx, "doctor", output))
