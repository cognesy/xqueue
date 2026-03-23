"""Job inspection CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from apps.cli.output import OutputFormat
from apps.cli.runtime import run_action
from libs.actions.jobs import (
    CancelJobAction,
    DeleteJobAction,
    ListJobsAction,
    PurgeJobsAction,
    RetryJobAction,
    ShowJobAction,
    TailJobLogsAction,
)
from libs.domain.models import AttemptLogStream, JobListFilters, JobListSort, JobState
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.services.config import ConfigLoader
from libs.services.database import SessionManager
from libs.services.job_logs import JobLogService
from libs.services.jobs import JobService
from libs.services.queues import QueueService


app = typer.Typer(help="Inspect queued and executed jobs.")


def _build_session_manager(use_workspace_instance: bool) -> SessionManager:
    config = ConfigLoader().load(
        workspace_root=Path.cwd(),
        use_workspace_instance=use_workspace_instance,
    )
    engine = create_sqlite_engine(config.paths.database_path)
    session_factory = create_session_factory(engine)
    return SessionManager(session_factory)


@app.command("list")
def list_jobs(
    queue: str | None = typer.Option(None, "--queue"),
    state: JobState | None = typer.Option(None, "--state"),
    worker_id: str | None = typer.Option(None, "--worker-id"),
    created_after: str | None = typer.Option(None, "--created-after", help="Inclusive ISO-8601 lower bound for created_at."),
    created_before: str | None = typer.Option(None, "--created-before", help="Inclusive ISO-8601 upper bound for created_at."),
    available_after: str | None = typer.Option(None, "--available-after", help="Inclusive ISO-8601 lower bound for available_at."),
    available_before: str | None = typer.Option(None, "--available-before", help="Inclusive ISO-8601 upper bound for available_at."),
    sort: JobListSort = typer.Option(JobListSort.CREATED_DESC, "--sort"),
    limit: int = typer.Option(50, "--limit", min=1, max=500),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """List jobs with optional queue and state filters."""
    action = ListJobsAction(_build_session_manager(use_workspace_instance), JobService())
    filters = JobListFilters(
        queue=queue,
        state=state,
        worker_id=worker_id,
        created_after=created_after,
        created_before=created_before,
        available_after=available_after,
        available_before=available_before,
        sort=sort,
        limit=limit,
    )
    run_action(lambda: action(filters), output_format=output)


@app.command("show")
def show_job(
    job_id: str = typer.Argument(..., metavar="JOB_ID"),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Show the detailed state for a single job."""
    action = ShowJobAction(_build_session_manager(use_workspace_instance), JobService())
    run_action(lambda: action(job_id), output_format=output)


@app.command("cancel")
def cancel_job(
    job_id: str = typer.Argument(..., metavar="JOB_ID"),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Cancel a queued job or request cancellation for a running job."""
    action = CancelJobAction(_build_session_manager(use_workspace_instance), JobService())
    run_action(lambda: action(job_id), output_format=output)


@app.command("retry")
def retry_job(
    job_id: str = typer.Argument(..., metavar="JOB_ID"),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Requeue a failed or canceled job."""
    action = RetryJobAction(_build_session_manager(use_workspace_instance), JobService())
    run_action(lambda: action(job_id), output_format=output)


@app.command("delete")
def delete_job(
    job_id: str = typer.Argument(..., metavar="JOB_ID"),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Delete a non-running job and its persisted history."""
    action = DeleteJobAction(
        _build_session_manager(use_workspace_instance),
        JobService(),
        JobLogService(),
    )
    run_action(lambda: action(job_id), output_format=output)


@app.command("tail")
def tail_job_logs(
    job_id: str = typer.Argument(..., metavar="JOB_ID"),
    stream: AttemptLogStream = typer.Option(AttemptLogStream.STDERR, "--stream"),
    lines: int = typer.Option(20, "--lines", min=1),
    attempt_number: int | None = typer.Option(None, "--attempt-number", min=1),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Tail one attempt log stream, defaulting to the latest attempt stderr."""
    action = TailJobLogsAction(
        _build_session_manager(use_workspace_instance),
        JobService(),
        JobLogService(),
    )
    run_action(
        lambda: action(
            job_id,
            stream=stream,
            lines=lines,
            attempt_number=attempt_number,
        ),
        output_format=output,
    )


@app.command("purge")
def purge_jobs(
    queue: str = typer.Option(..., "--queue"),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Delete queued or retry-scheduled jobs for a queue."""
    action = PurgeJobsAction(_build_session_manager(use_workspace_instance), QueueService())
    run_action(lambda: action(queue), output_format=output)
