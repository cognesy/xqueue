"""Queue inspection and control CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from apps.cli.output import OutputFormat
from apps.cli.runtime import run_action
from libs.actions.queues import ListQueueStatsAction, ListQueuesAction, PauseQueueAction, ResumeQueueAction
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.services.config import ConfigLoader
from libs.services.database import SessionManager
from libs.services.queues import QueueService


app = typer.Typer(help="Inspect and control queue state.")


def _build_session_manager(use_workspace_instance: bool) -> SessionManager:
    config = ConfigLoader().load(
        workspace_root=Path.cwd(),
        use_workspace_instance=use_workspace_instance,
    )
    engine = create_sqlite_engine(config.paths.database_path)
    session_factory = create_session_factory(engine)
    return SessionManager(session_factory)


@app.command("list")
def list_queues(
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """List known queues and their current state."""
    action = ListQueuesAction(_build_session_manager(use_workspace_instance), QueueService())
    run_action(action, output_format=output)


@app.command("stats")
def queue_stats(
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """List queue state and per-state job counts."""
    action = ListQueueStatsAction(_build_session_manager(use_workspace_instance), QueueService())
    run_action(action, output_format=output)


@app.command("pause")
def pause_queue(
    queue: str = typer.Argument(..., metavar="QUEUE"),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Pause a queue so new claims stop."""
    action = PauseQueueAction(_build_session_manager(use_workspace_instance), QueueService())
    run_action(lambda: action(queue), output_format=output)


@app.command("resume")
def resume_queue(
    queue: str = typer.Argument(..., metavar="QUEUE"),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Resume a paused queue."""
    action = ResumeQueueAction(_build_session_manager(use_workspace_instance), QueueService())
    run_action(lambda: action(queue), output_format=output)
