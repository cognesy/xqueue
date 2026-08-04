from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from xqueue.adapters.filesystem.metrics import MetricsService
from xqueue.adapters.sqlite.database import create_session_factory, create_sqlite_engine
from xqueue.adapters.sqlite.models import AttemptModel, Base, EventModel, JobModel
from xqueue.adapters.sqlite.session import SessionManager
from xqueue.jobs.store import JobService
from xqueue.queues.actions import (
    ListQueuesAction,
    ListQueueStatsAction,
    PauseQueueAction,
    PurgeJobsAction,
    ResumeQueueAction,
)
from xqueue.queues.store import QueueService
from xqueue.workers.attempts import AttemptService
from xqueue.workers.models import RegisterWorkerInput
from xqueue.workers.orchestration import RunWorkerAction
from xqueue.workers.process import CommandExecutionService
from xqueue.workers.store import WorkerService


def test_queue_actions_list_and_stats_include_job_counts(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 40, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add_all(
            [
                JobModel(
                    id="job-1",
                    queue="alpha",
                    command="echo one",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="queued",
                ),
                JobModel(
                    id="job-2",
                    queue="alpha",
                    command="echo two",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="running",
                ),
                JobModel(
                    id="job-3",
                    queue="beta",
                    command="echo three",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="failed",
                ),
            ]
        )

    list_action = ListQueuesAction(SessionManager(session_factory), QueueService())
    stats_action = ListQueueStatsAction(SessionManager(session_factory), QueueService())

    listed = list_action()
    stats = stats_action()

    assert [item.name for item in listed] == ["alpha", "beta"]
    alpha_stats = next(item for item in stats if item.name == "alpha")
    beta_stats = next(item for item in stats if item.name == "beta")
    assert alpha_stats.total_jobs == 2
    assert alpha_stats.queued_jobs == 1
    assert alpha_stats.running_jobs == 1
    assert beta_stats.failed_jobs == 1
    assert alpha_stats.timed_out_jobs == 0
    assert alpha_stats.dead_jobs == 0


def test_queue_stats_counts_timed_out_and_dead_jobs(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 42, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add_all(
            [
                JobModel(
                    id="job-timed-out",
                    queue="gamma",
                    command="sleep 999",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="timed_out",
                ),
                JobModel(
                    id="job-dead",
                    queue="gamma",
                    command="echo dead",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="dead",
                ),
            ]
        )

    stats_action = ListQueueStatsAction(SessionManager(session_factory), QueueService())
    stats = stats_action()

    gamma_stats = next(item for item in stats if item.name == "gamma")
    assert gamma_stats.total_jobs == 2
    assert gamma_stats.timed_out_jobs == 1
    assert gamma_stats.dead_jobs == 1
    assert gamma_stats.failed_jobs == 0


def test_paused_queue_blocks_claims_until_resumed(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 45, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-1",
                queue="alpha",
                command="echo one",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="queued",
            )
        )

    pause_action = PauseQueueAction(SessionManager(session_factory), QueueService(), clock=lambda: now)
    resume_action = ResumeQueueAction(SessionManager(session_factory), QueueService(), clock=lambda: now)
    worker_action = RunWorkerAction(
        SessionManager(session_factory),
        WorkerService(JobService(), QueueService()),
        job_service=JobService(),
        attempt_service=AttemptService(JobService()),
        execution_service=CommandExecutionService(),
        log_root=tmp_path / "logs",
        metrics=MetricsService(tmp_path / "metrics.json"),
        clock=lambda: now,
    )

    pause_result = pause_action("alpha")
    assert pause_result.state.value == "paused"

    blocked = worker_action(
        RegisterWorkerInput(worker_id="worker-1", queues=["alpha"]),
        lease_duration_seconds=30,
    )
    assert blocked.claimed_job is None

    resume_result = resume_action("alpha")
    assert resume_result.state.value == "active"

    claimed = worker_action(
        RegisterWorkerInput(worker_id="worker-1", queues=["alpha"]),
        lease_duration_seconds=30,
    )
    assert claimed.claimed_job is not None
    assert claimed.claimed_job.id == "job-1"


def test_purge_jobs_action_deletes_only_queued_and_retry_scheduled_jobs(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 50, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add_all(
            [
                JobModel(
                    id="job-queued",
                    queue="alpha",
                    command="echo queued",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="queued",
                ),
                JobModel(
                    id="job-retry",
                    queue="alpha",
                    command="echo retry",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now + timedelta(seconds=5),
                    state="retry_scheduled",
                ),
                JobModel(
                    id="job-running",
                    queue="alpha",
                    command="echo running",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="running",
                ),
            ]
        )

    action = PurgeJobsAction(SessionManager(session_factory), QueueService())
    result = action("alpha")

    assert result.queue == "alpha"
    assert result.deleted_count == 2

    with engine.connect() as connection:
        remaining = connection.execute(
            text("SELECT id, state FROM jobs WHERE queue = :queue ORDER BY id"),
            {"queue": "alpha"},
        ).all()

    assert [(row.id, row.state) for row in remaining] == [("job-running", "running")]


def test_purge_jobs_succeeds_when_retry_scheduled_job_has_attempts(tmp_path: Path) -> None:
    """Regression: purge must cascade-delete attempts and events before deleting jobs."""
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 55, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        retry_job = JobModel(
            id="job-retry-with-attempt",
            queue="alpha",
            command="echo retry",
            shell=True,
            priority=10,
            attempt_count=1,
            created_at=now,
            available_at=now + timedelta(seconds=5),
            state="retry_scheduled",
        )
        session.add(retry_job)
        session.flush()
        attempt = AttemptModel(
            job_id="job-retry-with-attempt",
            attempt_number=1,
            state="failed",
            started_at=now,
            finished_at=now,
            exit_code=1,
            error="command exited with code 1",
        )
        session.add(attempt)
        session.flush()
        event = EventModel(
            event_type="job.failed",
            created_at=now,
            job_id="job-retry-with-attempt",
            attempt_id=attempt.id,
        )
        session.add(event)

    action = PurgeJobsAction(SessionManager(session_factory), QueueService())
    result = action("alpha")

    assert result.queue == "alpha"
    assert result.deleted_count == 1

    with engine.connect() as connection:
        from sqlalchemy import text

        assert connection.execute(text("SELECT COUNT(*) FROM jobs WHERE queue = 'alpha'")).scalar() == 0
        assert (
            connection.execute(text("SELECT COUNT(*) FROM attempts WHERE job_id = 'job-retry-with-attempt'")).scalar()
            == 0
        )
        assert (
            connection.execute(text("SELECT COUNT(*) FROM events WHERE job_id = 'job-retry-with-attempt'")).scalar()
            == 0
        )
