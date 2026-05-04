"""Helpers for the content-first bare xq home view."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from sqlalchemy import select

from xqueue_libs.domain.models import JobState, WorkerState
from xqueue_libs.domain.responses import HomeJobCount, HomeQueueRow, HomeResponse, HomeWorkerRow
from xqueue_libs.infra.database import create_session_factory, create_sqlite_engine
from xqueue_libs.infra.models import JobModel
from xqueue_libs.services.config import ConfigLoader
from xqueue_libs.services.database import SessionManager
from xqueue_libs.services.queues import QueueService
from xqueue_libs.services.workers import WorkerService


def collapse_home_path(path: str) -> str:
    """Collapse the user home directory for human-readable paths."""
    home = str(Path.home())
    return path.replace(home, "~", 1) if path.startswith(home) else path


def resolve_executable() -> str:
    """Resolve the absolute xq executable path."""
    which = shutil.which("xq")
    if which:
        return collapse_home_path(str(Path(which).resolve()))
    return collapse_home_path(str(Path(sys.argv[0]).resolve()))


def _prefer_workspace_instance(workspace_root: Path) -> bool:
    return (workspace_root / "instance" / "xqueue.db").exists()


def build_home_response(workspace_root: Path) -> HomeResponse:
    """Build the compact content-first home response for the current workspace."""
    use_workspace_instance = _prefer_workspace_instance(workspace_root)
    help_items = [
        "Run `xq jobs show <job_id>` for full job details",
        "Run `xq enqueue --queue <queue> -- <command>` to add work",
        "Run `xq workers list` to inspect worker state",
    ]

    try:
        config = ConfigLoader().load(
            workspace_root=workspace_root,
            use_workspace_instance=use_workspace_instance,
        )
        engine = create_sqlite_engine(config.paths.database_path)
        session_factory = create_session_factory(engine)
        session_manager = SessionManager(session_factory)
        queue_service = QueueService()
        worker_service = WorkerService()

        with session_manager.session() as session:
            queue_stats = queue_service.list_queue_stats(session)
            workers = worker_service.list_workers(session)
            running_jobs = session.execute(
                select(JobModel.worker_id, JobModel.command)
                .where(JobModel.state == JobState.RUNNING.value)
                .where(JobModel.worker_id.is_not(None))
            ).all()
            worker_commands: dict[str, str] = {row.worker_id: row.command for row in running_jobs}
    except Exception:
        queue_stats = []
        workers = []
        worker_commands = {}
        help_items.append("Run `xq db check` to inspect the current state store")

    job_counts = {
        JobState.QUEUED: 0,
        JobState.RUNNING: 0,
        JobState.RETRY_SCHEDULED: 0,
        JobState.SUCCEEDED: 0,
        JobState.FAILED: 0,
        JobState.CANCELED: 0,
    }
    for queue in queue_stats:
        job_counts[JobState.QUEUED] += queue.queued_jobs
        job_counts[JobState.RUNNING] += queue.running_jobs
        job_counts[JobState.RETRY_SCHEDULED] += queue.retry_scheduled_jobs
        job_counts[JobState.SUCCEEDED] += queue.succeeded_jobs
        job_counts[JobState.FAILED] += queue.failed_jobs
        job_counts[JobState.CANCELED] += queue.canceled_jobs

    return HomeResponse(
        bin=resolve_executable(),
        description="CLI-first durable work queue for shell commands in the current workspace",
        queues=[
            HomeQueueRow(
                name=queue.name,
                state=queue.state,
                total_jobs=queue.total_jobs,
                running_jobs=queue.running_jobs,
                queued_jobs=queue.queued_jobs,
            )
            for queue in queue_stats
        ],
        jobs=[
            HomeJobCount(state=state, count=count)
            for state, count in job_counts.items()
        ],
        workers=[
            HomeWorkerRow(
                id=worker.id,
                state=worker.state,
                queues=list(worker.queues),
                heartbeat_at=None if worker.heartbeat_at is None else worker.heartbeat_at.isoformat(),
                current_command=worker_commands.get(worker.id),
            )
            for worker in workers
            if worker.state is WorkerState.ACTIVE
        ],
        help=help_items,
    )
