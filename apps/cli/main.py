"""Thin Typer entrypoint for the xqueue CLI."""

from __future__ import annotations

import typer

from apps.cli.commands.enqueue import register as register_enqueue
from apps.cli.commands.db import app as db_app
from apps.cli.commands.config import app as config_app
from apps.cli.commands.controller import app as controller_app
from apps.cli.commands.doctor import register as register_doctor
from apps.cli.commands.health import register as register_health
from apps.cli.commands.jobs import app as jobs_app
from apps.cli.commands.queues import app as queues_app
from apps.cli.commands.recover import app as recover_app
from apps.cli.commands.worker import app as worker_app
from apps.cli.commands.workers import app as workers_app
from libs.services.logging import configure_logging

app = typer.Typer(
    name="xq",
    help="CLI-first durable work queue for shell commands.",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")
app.add_typer(controller_app, name="controller")
app.add_typer(db_app, name="db")
app.add_typer(jobs_app, name="jobs")
app.add_typer(queues_app, name="queues")
app.add_typer(recover_app, name="recover")
app.add_typer(worker_app, name="worker")
app.add_typer(workers_app, name="workers")
register_enqueue(app)
register_health(app)
register_doctor(app)


@app.callback()
def callback() -> None:
    """Top-level xq command group."""
    configure_logging()


def main() -> None:
    """Console script entrypoint."""
    app()
