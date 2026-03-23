"""Worker runtime CLI commands."""

from __future__ import annotations

import os
import socket
from pathlib import Path
from uuid import uuid4

import typer

from apps.cli.output import OutputFormat
from apps.cli.runtime import run_action
from libs.actions.workers import RunWorkerAction, RunWorkerLoopAction
from libs.domain.errors import ValidationError
from libs.domain.models import RegisterWorkerInput
from libs.services.attempts import AttemptService
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.services.config import ConfigLoader
from libs.services.database import SessionManager
from libs.services.execution import CommandExecutionService
from libs.services.jobs import JobService
from libs.services.workers import WorkerService


app = typer.Typer(
    help="Run and inspect local worker processes.",
    invoke_without_command=True,
    no_args_is_help=True,
)


def _default_worker_id() -> str:
    return f"worker-{os.getpid()}-{uuid4().hex[:8]}"


def _validate_concurrency_mode(*, concurrency: int, continuous: bool, execute_claimed: bool) -> None:
    if concurrency <= 1:
        return
    if not continuous or not execute_claimed:
        raise ValidationError(
            "worker concurrency greater than 1 is only supported with --continuous and --execute-claimed",
            details={
                "concurrency": concurrency,
                "continuous": continuous,
                "execute_claimed": execute_claimed,
            },
        )


def _run_worker_command(
    worker_id: str | None = typer.Option(None, "--worker-id"),
    queue: list[str] = typer.Option(None, "--queue"),
    concurrency: int = typer.Option(1, "--concurrency", min=1),
    lease_seconds: int = typer.Option(30, "--lease-seconds", min=1),
    execute_claimed: bool = typer.Option(False, "--execute-claimed"),
    continuous: bool = typer.Option(False, "--continuous"),
    poll_interval_seconds: float | None = typer.Option(None, "--poll-interval-seconds", min=0.001),
    default_timeout_seconds: int | None = typer.Option(None, "--default-timeout-seconds", min=1),
    cancel_grace_period_seconds: int | None = typer.Option(None, "--cancel-grace-period-seconds", min=1),
    retry_delay_seconds: int | None = typer.Option(None, "--retry-delay-seconds", min=0),
    max_polls: int | None = typer.Option(None, "--max-polls", min=1, hidden=True),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Register a worker and perform one claim poll."""
    def execute():
        _validate_concurrency_mode(
            concurrency=concurrency,
            continuous=continuous,
            execute_claimed=execute_claimed,
        )

        config = ConfigLoader().load(
            workspace_root=Path.cwd(),
            use_workspace_instance=use_workspace_instance,
        )
        engine = create_sqlite_engine(config.paths.database_path)
        session_factory = create_session_factory(engine)
        job_service = JobService()
        run_worker_action = RunWorkerAction(
            SessionManager(session_factory),
            WorkerService(job_service),
            job_service=job_service,
            attempt_service=AttemptService(job_service),
            execution_service=CommandExecutionService(),
            log_root=config.paths.log_root,
            default_timeout_seconds=config.worker.default_timeout_seconds if default_timeout_seconds is None else default_timeout_seconds,
            cancel_grace_period_seconds=config.worker.cancel_grace_period_seconds if cancel_grace_period_seconds is None else cancel_grace_period_seconds,
            retry_delay_seconds=config.worker.retry_delay_seconds if retry_delay_seconds is None else retry_delay_seconds,
        )
        loop_action = RunWorkerLoopAction(run_worker_action)

        payload = RegisterWorkerInput(
            worker_id=worker_id or _default_worker_id(),
            queues=queue or [config.queue.default_queue],
            concurrency=concurrency,
            hostname=socket.gethostname(),
            process_id=os.getpid(),
        )

        if continuous:
            return loop_action(
                payload,
                lease_duration_seconds=lease_seconds,
                poll_interval_seconds=config.worker.poll_interval_seconds if poll_interval_seconds is None else poll_interval_seconds,
                execute_claimed=execute_claimed,
                max_polls=max_polls,
            )

        return run_worker_action(
            payload,
            lease_duration_seconds=lease_seconds,
            execute_claimed=execute_claimed,
        )

    run_action(execute, output_format=output)


@app.callback()
def worker_callback(
    ctx: typer.Context,
    worker_id: str | None = typer.Option(None, "--worker-id"),
    queue: list[str] = typer.Option(None, "--queue"),
    concurrency: int = typer.Option(1, "--concurrency", min=1),
    lease_seconds: int = typer.Option(30, "--lease-seconds", min=1),
    execute_claimed: bool = typer.Option(False, "--execute-claimed"),
    continuous: bool = typer.Option(False, "--continuous"),
    poll_interval_seconds: float | None = typer.Option(None, "--poll-interval-seconds", min=0.001),
    default_timeout_seconds: int | None = typer.Option(None, "--default-timeout-seconds", min=1),
    cancel_grace_period_seconds: int | None = typer.Option(None, "--cancel-grace-period-seconds", min=1),
    retry_delay_seconds: int | None = typer.Option(None, "--retry-delay-seconds", min=0),
    max_polls: int | None = typer.Option(None, "--max-polls", min=1, hidden=True),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Run a worker directly when invoked without a subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    _run_worker_command(
        worker_id=worker_id,
        queue=queue,
        concurrency=concurrency,
        lease_seconds=lease_seconds,
        execute_claimed=execute_claimed,
        continuous=continuous,
        poll_interval_seconds=poll_interval_seconds,
        default_timeout_seconds=default_timeout_seconds,
        cancel_grace_period_seconds=cancel_grace_period_seconds,
        retry_delay_seconds=retry_delay_seconds,
        max_polls=max_polls,
        output=output,
        use_workspace_instance=use_workspace_instance,
    )


@app.command("run")
def run_worker(
    worker_id: str | None = typer.Option(None, "--worker-id"),
    queue: list[str] = typer.Option(None, "--queue"),
    concurrency: int = typer.Option(1, "--concurrency", min=1),
    lease_seconds: int = typer.Option(30, "--lease-seconds", min=1),
    execute_claimed: bool = typer.Option(False, "--execute-claimed"),
    continuous: bool = typer.Option(False, "--continuous"),
    poll_interval_seconds: float | None = typer.Option(None, "--poll-interval-seconds", min=0.001),
    default_timeout_seconds: int | None = typer.Option(None, "--default-timeout-seconds", min=1),
    cancel_grace_period_seconds: int | None = typer.Option(None, "--cancel-grace-period-seconds", min=1),
    retry_delay_seconds: int | None = typer.Option(None, "--retry-delay-seconds", min=0),
    max_polls: int | None = typer.Option(None, "--max-polls", min=1, hidden=True),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Register a worker and perform one claim poll."""
    _run_worker_command(
        worker_id=worker_id,
        queue=queue,
        concurrency=concurrency,
        lease_seconds=lease_seconds,
        execute_claimed=execute_claimed,
        continuous=continuous,
        poll_interval_seconds=poll_interval_seconds,
        default_timeout_seconds=default_timeout_seconds,
        cancel_grace_period_seconds=cancel_grace_period_seconds,
        retry_delay_seconds=retry_delay_seconds,
        max_polls=max_polls,
        output=output,
        use_workspace_instance=use_workspace_instance,
    )
