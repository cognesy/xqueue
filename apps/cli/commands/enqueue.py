"""Top-level enqueue command."""

from __future__ import annotations

import shlex
from pathlib import Path

import typer

from apps.cli.output import Output, OutputFormat
from apps.cli.runtime import run_action
from libs.actions.jobs import EnqueueJobAction
from libs.domain.errors import ValidationError
from libs.domain.models import EnqueueJobInput
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.services.config import ConfigLoader
from libs.services.database import SessionManager
from libs.services.jobs import JobService


def _parse_env_items(items: list[str]) -> dict[str, str] | None:
    if not items:
        return None

    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValidationError("environment items must use KEY=VALUE format", details={"item": item})
        key, value = item.split("=", 1)
        if not key:
            raise ValidationError("environment keys must not be empty", details={"item": item})
        parsed[key] = value
    return parsed


def register(app: typer.Typer) -> None:
    @app.command(
        "enqueue",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def enqueue(
        ctx: typer.Context,
        queue: str = typer.Option(..., "--queue"),
        cwd: Path | None = typer.Option(None, "--cwd"),
        priority: int = typer.Option(100, "--priority"),
        timeout_seconds: int | None = typer.Option(None, "--timeout-seconds"),
        max_attempts: int = typer.Option(1, "--max-attempts"),
        created_by: str | None = typer.Option(None, "--created-by"),
        env: list[str] = typer.Option(None, "--env"),
        output: OutputFormat | None = typer.Option(None, "--output", "-o"),
        use_workspace_instance: bool = typer.Option(
            False,
            "--workspace-instance",
            help="Resolve runtime paths relative to the repository instance directory.",
            hidden=True,
        ),
    ) -> None:
        """Persist a queued command job."""
        config = ConfigLoader().load(
            workspace_root=Path.cwd(),
            use_workspace_instance=use_workspace_instance,
        )
        engine = create_sqlite_engine(config.paths.database_path)
        session_factory = create_session_factory(engine)
        action = EnqueueJobAction(SessionManager(session_factory), JobService())

        def execute() -> object:
            if not ctx.args:
                raise ValidationError("enqueue requires a command after '--'")

            payload = EnqueueJobInput(
                queue=queue,
                command=shlex.join(ctx.args),
                shell=True,
                cwd=str(cwd) if cwd is not None else None,
                env=_parse_env_items(env),
                priority=priority,
                timeout_seconds=timeout_seconds,
                max_attempts=max_attempts,
                created_by=created_by,
            )
            return action(payload)

        run_action(execute, out=Output(ctx, "enqueue", output))
