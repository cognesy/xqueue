"""Thin Typer entrypoint for the xqueue CLI."""

from __future__ import annotations

from pathlib import Path

import typer

from apps.cli.home import build_home_response
from apps.cli.output import Output, OutputFormat
from apps.cli.commands.enqueue import register as register_enqueue
from apps.cli.commands.db import app as db_app
from apps.cli.commands.config import app as config_app
from apps.cli.commands.controller import app as controller_app
from apps.cli.commands.doctor import register as register_doctor
from apps.cli.commands.health import register as register_health
from apps.cli.commands.hooks import app as hooks_app
from apps.cli.commands.jobs import app as jobs_app
from apps.cli.commands.metrics import app as metrics_app
from apps.cli.commands.queues import app as queues_app
from apps.cli.commands.recover import app as recover_app
from apps.cli.commands.worker import app as worker_app
from apps.cli.commands.workers import app as workers_app
from libs.services.logging import configure_logging

app = typer.Typer(
    name="xq",
    help="CLI-first durable work queue for shell commands.",
    invoke_without_command=True,
)
app.add_typer(config_app, name="config")
app.add_typer(controller_app, name="controller")
app.add_typer(db_app, name="db")
app.add_typer(hooks_app, name="hooks")
app.add_typer(jobs_app, name="jobs")
app.add_typer(metrics_app, name="metrics")
app.add_typer(queues_app, name="queues")
app.add_typer(recover_app, name="recover")
app.add_typer(worker_app, name="worker")
app.add_typer(workers_app, name="workers")
register_enqueue(app)
register_health(app)
register_doctor(app)


@app.callback()
def callback(
    ctx: typer.Context,
    output: OutputFormat = typer.Option(OutputFormat.TOON, "--output", "-o"),
    fields: str | None = typer.Option(None, "--fields"),
    full: bool = typer.Option(False, "--full"),
) -> None:
    """Top-level xq command group."""
    ctx.obj = {
        "output": output,
        "fields": fields,
        "full": full,
    }
    configure_logging()
    if ctx.invoked_subcommand is None:
        Output(ctx, "home").print(build_home_response(Path.cwd()))


def main() -> None:
    """Console script entrypoint."""
    app()
