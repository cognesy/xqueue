"""Worker runtime CLI commands."""

from __future__ import annotations

import os
import socket
from uuid import uuid4

import typer
from xqueue.core.errors import ValidationError
from xqueue.workers.models import RegisterWorkerInput, WorkerPollResult
from xqueue_cli.client import open_client
from xqueue_cli.contracts import DetailResponse
from xqueue_cli.output import Output, OutputFormat
from xqueue_cli.runtime import run_action

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
    ctx: typer.Context,
    contract_name: str,
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
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Register a worker and perform one claim poll."""
    out = Output(ctx, contract_name, output)

    def execute() -> DetailResponse[WorkerPollResult]:
        _validate_concurrency_mode(
            concurrency=concurrency,
            continuous=continuous,
            execute_claimed=execute_claimed,
        )

        with open_client(use_workspace_instance=use_workspace_instance) as xq:
            config = xq.workspace.config()
            payload = RegisterWorkerInput(
                worker_id=worker_id or _default_worker_id(),
                queues=queue or [config.queue.default_queue],
                concurrency=concurrency,
                hostname=socket.gethostname(),
                process_id=os.getpid(),
            )
            result = xq.workers.run(
                payload,
                lease_duration_seconds=lease_seconds,
                execute_claimed=execute_claimed,
                continuous=continuous,
                poll_interval_seconds=poll_interval_seconds,
                max_polls=max_polls,
                default_timeout_seconds=default_timeout_seconds,
                cancel_grace_period_seconds=cancel_grace_period_seconds,
                retry_delay_seconds=retry_delay_seconds,
            )
            return DetailResponse(item=result)

    run_action(execute, out=out)


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
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
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
        ctx,
        "worker",
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
    output: OutputFormat | None = typer.Option(None, "--output", "-o"),
    use_workspace_instance: bool = typer.Option(
        False,
        "--workspace-instance",
        help="Resolve runtime paths relative to the repository instance directory.",
        hidden=True,
    ),
) -> None:
    """Register a worker and perform one claim poll."""
    _run_worker_command(
        ctx,
        "worker.run",
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
