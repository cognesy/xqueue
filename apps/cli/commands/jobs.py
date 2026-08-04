"""Job inspection CLI commands."""

from __future__ import annotations

from datetime import datetime

import typer
from xqueue.core.errors import ValidationError
from xqueue.jobs.models import AttemptLogStream, JobListFilters, JobListSort, JobState, JobSummary
from xqueue_cli.client import open_client
from xqueue_cli.contracts import DetailResponse, ListResponse, MutationResponse
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action

app = typer.Typer(help="Inspect queued and executed jobs.")


def _parse_timestamp(value: str | None, *, option: str) -> datetime | None:
    """Parse an ISO-8601 option so bad input is a mapped error, not a traceback."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(
            f"{option} must be an ISO-8601 timestamp",
            details={"option": option, "value": value},
        ) from exc


@app.command("list")
def list_jobs(
    ctx: typer.Context,
    queue: str | None = typer.Option(None, "--queue"),
    state: JobState | None = typer.Option(None, "--state"),
    worker_id: str | None = typer.Option(None, "--worker-id"),
    created_after: str | None = typer.Option(
        None, "--created-after", help="Inclusive ISO-8601 lower bound for created_at."
    ),
    created_before: str | None = typer.Option(
        None, "--created-before", help="Inclusive ISO-8601 upper bound for created_at."
    ),
    available_after: str | None = typer.Option(
        None, "--available-after", help="Inclusive ISO-8601 lower bound for available_at."
    ),
    available_before: str | None = typer.Option(
        None, "--available-before", help="Inclusive ISO-8601 upper bound for available_at."
    ),
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

    def _list() -> ListResponse[JobSummary]:
        filters = JobListFilters(
            queue=queue,
            state=state,
            worker_id=worker_id,
            created_after=_parse_timestamp(created_after, option="--created-after"),
            created_before=_parse_timestamp(created_before, option="--created-before"),
            available_after=_parse_timestamp(available_after, option="--available-after"),
            available_before=_parse_timestamp(available_before, option="--available-before"),
            sort=sort,
            limit=limit,
        )
        return ListResponse(items=xq.jobs.list(filters))

    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(_list, out=Output(ctx, "jobs.list", output))


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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(lambda: DetailResponse(item=xq.jobs.show(job_id)), out=Output(ctx, "jobs.show", output))


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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(lambda: DetailResponse(item=xq.jobs.pane(job_id)), out=Output(ctx, "jobs.pane", output))


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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(lambda: MutationResponse(item=xq.jobs.cancel(job_id)), out=Output(ctx, "jobs.cancel", output))


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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(lambda: MutationResponse(item=xq.jobs.retry(job_id)), out=Output(ctx, "jobs.retry", output))


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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(lambda: MutationResponse(item=xq.jobs.delete(job_id)), out=Output(ctx, "jobs.delete", output))


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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(
            lambda: DetailResponse(
                item=xq.jobs.tail(
                    job_id,
                    stream=stream,
                    lines=lines,
                    attempt_number=attempt_number,
                )
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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(lambda: MutationResponse(item=xq.queues.purge(queue)), out=Output(ctx, "jobs.purge", output))


@app.command("prune")
def prune_jobs(
    ctx: typer.Context,
    state: str | None = typer.Option(
        None, "--state", help="Job state to prune (e.g. failed, succeeded, canceled, terminal)."
    ),
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
    with open_client(use_workspace_instance=use_workspace_instance) as xq:
        run_action(
            lambda: MutationResponse(
                item=xq.jobs.prune(
                    state=state,
                    older_than=older_than,
                    prune_logs=logs,
                    dry_run=not apply,
                )
            ),
            out=Output(ctx, "jobs.prune", output),
        )
