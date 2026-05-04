"""Job inspection CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action
from xqueue_libs.actions.jobs import (
    CancelJobAction,
    DeleteJobAction,
    JobPaneAction,
    ListJobsAction,
    PruneJobsAction,
    PurgeJobsAction,
    RetryJobAction,
    ShowJobAction,
    TailJobLogsAction,
)
from xqueue_libs.domain.models import AttemptLogStream, JobListFilters, JobListSort, JobState
from xqueue_libs.infra.database import create_session_factory, create_sqlite_engine
from xqueue_libs.services.config import ConfigLoader
from xqueue_libs.services.database import SessionManager
from xqueue_libs.services.job_logs import JobLogService
from xqueue_libs.services.jobs import JobService
from xqueue_libs.services.pruning import JobPruningService
from xqueue_libs.services.queues import QueueService


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
    ctx: typer.Context,
    queue: str | None = typer.Option(None, "--queue"),
    state: JobState | None = typer.Option(None, "--state"),
    worker_id: str | None = typer.Option(None, "--worker-id"),
    created_after: str | None = typer.Option(None, "--created-after", help="Inclusive ISO-8601 lower bound for created_at."),
    created_before: str | None = typer.Option(None, "--created-before", help="Inclusive ISO-8601 upper bound for created_at."),
    available_after: str | None = typer.Option(None, "--available-after", help="Inclusive ISO-8601 lower bound for available_at."),
    available_before: str | None = typer.Option(None, "--available-before", help="Inclusive ISO-8601 upper bound for available_at."),
    sort: JobListSort = typer.Option(JobListSort.CREATED_DESC, "--sort"),
    limit: int = typer.Option(50, "--limit", min=1, max=500),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
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
    run_action(lambda: action(filters), out=Output(ctx, "jobs.list", output))


@app.command("show")
def show_job(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., metavar="JOB_ID"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Show the detailed state for a single job."""
    action = ShowJobAction(_build_session_manager(use_workspace_instance), JobService())
    run_action(lambda: action(job_id), out=Output(ctx, "jobs.show", output))


@app.command("pane")
def job_pane(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., metavar="JOB_ID"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Show concise job liveness for monitor panes."""
    action = JobPaneAction(_build_session_manager(use_workspace_instance), JobService())
    run_action(lambda: action(job_id), out=Output(ctx, "jobs.pane", output))


@app.command("cancel")
def cancel_job(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., metavar="JOB_ID"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Cancel a queued job or request cancellation for a running job."""
    action = CancelJobAction(_build_session_manager(use_workspace_instance), JobService())
    run_action(lambda: action(job_id), out=Output(ctx, "jobs.cancel", output))


@app.command("retry")
def retry_job(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., metavar="JOB_ID"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Requeue a failed or canceled job."""
    action = RetryJobAction(_build_session_manager(use_workspace_instance), JobService())
    run_action(lambda: action(job_id), out=Output(ctx, "jobs.retry", output))


@app.command("delete")
def delete_job(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., metavar="JOB_ID"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
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
    run_action(lambda: action(job_id), out=Output(ctx, "jobs.delete", output))


@app.command("tail")
def tail_job_logs(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., metavar="JOB_ID"),
    stream: AttemptLogStream = typer.Option(AttemptLogStream.STDERR, "--stream"),
    lines: int = typer.Option(20, "--lines", min=1),
    attempt_number: int | None = typer.Option(None, "--attempt-number", min=1),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
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
        out=Output(ctx, "jobs.tail", output),
    )


@app.command("purge")
def purge_jobs(
    ctx: typer.Context,
    queue: str = typer.Option(..., "--queue"),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Delete queued or retry-scheduled jobs for a queue."""
    action = PurgeJobsAction(_build_session_manager(use_workspace_instance), QueueService())
    run_action(lambda: action(queue), out=Output(ctx, "jobs.purge", output))


@app.command("prune")
def prune_jobs(
    ctx: typer.Context,
    state: str | None = typer.Option(None, "--state", help="Job state to prune (e.g. failed, succeeded, canceled, terminal)."),
    older_than: str | None = typer.Option(None, "--older-than", help="Duration threshold, e.g. 24h, 7d, 30m."),
    logs: bool = typer.Option(False, "--logs", help="Also delete associated attempt log files."),
    apply: bool = typer.Option(False, "--apply", help="Execute the prune. Without this flag, runs as dry-run."),
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Prune terminal job history. Dry-run by default; pass --apply to execute."""
    action = PruneJobsAction(
        _build_session_manager(use_workspace_instance),
        JobPruningService(),
        JobLogService(),
    )
    run_action(
        lambda: action(
            state=state,
            older_than=older_than,
            prune_logs=logs,
            dry_run=not apply,
        ),
        out=Output(ctx, "jobs.prune", output),
    )
