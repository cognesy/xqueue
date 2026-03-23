"""Worker inspection and control CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from apps.cli.output import OutputFormat
from apps.cli.runtime import run_action
from libs.actions.workers import ListWorkersAction, SetWorkerStateAction
from libs.domain.models import WorkerState
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.services.config import ConfigLoader
from libs.services.database import SessionManager
from libs.services.workers import WorkerService


app = typer.Typer(help="Inspect and control persisted worker state.")


def _build_session_manager(use_workspace_instance: bool) -> SessionManager:
    config = ConfigLoader().load(
        workspace_root=Path.cwd(),
        use_workspace_instance=use_workspace_instance,
    )
    engine = create_sqlite_engine(config.paths.database_path)
    session_factory = create_session_factory(engine)
    return SessionManager(session_factory)


@app.command("list")
def list_workers(
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """List workers with queues, heartbeat, and operational state."""
    action = ListWorkersAction(_build_session_manager(use_workspace_instance), WorkerService())
    run_action(action, output_format=output)


def _set_state_command(state: WorkerState):
    def command(
        worker_id: str = typer.Argument(..., metavar="WORKER_ID"),
        output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
        use_workspace_instance: bool = typer.Option(
            False,
            "--workspace-instance",
            help="Resolve runtime paths relative to the repository instance directory.",
            hidden=True,
        ),
    ) -> None:
        """Persist a worker state change."""
        action = SetWorkerStateAction(_build_session_manager(use_workspace_instance), WorkerService())
        run_action(lambda: action(worker_id, state), output_format=output)

    return command


app.command("pause")(_set_state_command(WorkerState.PAUSED))
app.command("resume")(_set_state_command(WorkerState.ACTIVE))
app.command("drain")(_set_state_command(WorkerState.DRAINING))
app.command("stop")(_set_state_command(WorkerState.STOPPED))
