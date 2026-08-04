from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from xqueue.adapters.filesystem.metrics import MetricsService
from xqueue.adapters.sqlite.database import create_session_factory, create_sqlite_engine
from xqueue.adapters.sqlite.models import Base, JobModel
from xqueue.adapters.sqlite.session import SessionManager
from xqueue.jobs.store import JobService
from xqueue.queues.store import QueueService
from xqueue.workers.attempts import AttemptService
from xqueue.workers.models import RegisterWorkerInput, WorkerState
from xqueue.workers.orchestration import ListWorkersAction, RegisterWorkerAction, RunWorkerAction, SetWorkerStateAction
from xqueue.workers.process import CommandExecutionService
from xqueue.workers.store import WorkerService


def test_worker_control_actions_list_and_change_states(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 22, 10, tzinfo=UTC)

    register_action = RegisterWorkerAction(
        SessionManager(session_factory),
        WorkerService(),
        clock=lambda: now,
    )
    set_state_action = SetWorkerStateAction(
        SessionManager(session_factory),
        WorkerService(),
        clock=lambda: now,
    )
    list_action = ListWorkersAction(SessionManager(session_factory), WorkerService())

    register_action(RegisterWorkerInput(worker_id="worker-1", queues=["agent"]))
    set_state_action("worker-1", WorkerState.PAUSED)
    set_state_action("worker-1", WorkerState.DRAINING)

    result = list_action()

    assert len(result) == 1
    assert result[0].id == "worker-1"
    assert result[0].state.value == "draining"


def test_paused_worker_id_does_not_claim_jobs_until_resumed(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 22, 15, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-1",
                queue="agent",
                command="echo one",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="queued",
            )
        )

    register_action = RegisterWorkerAction(
        SessionManager(session_factory),
        WorkerService(),
        clock=lambda: now,
    )
    set_state_action = SetWorkerStateAction(
        SessionManager(session_factory),
        WorkerService(),
        clock=lambda: now,
    )
    run_action = RunWorkerAction(
        SessionManager(session_factory),
        WorkerService(JobService(), QueueService()),
        job_service=JobService(),
        attempt_service=AttemptService(JobService()),
        execution_service=CommandExecutionService(),
        log_root=tmp_path / "logs",
        metrics=MetricsService(tmp_path / "metrics.json"),
        clock=lambda: now,
    )

    register_action(RegisterWorkerInput(worker_id="worker-1", queues=["agent"]))
    set_state_action("worker-1", WorkerState.PAUSED)

    paused_result = run_action(
        RegisterWorkerInput(worker_id="worker-1", queues=["agent"]),
        lease_duration_seconds=30,
    )
    assert paused_result.worker.state.value == "paused"
    assert paused_result.claimed_job is None

    set_state_action("worker-1", WorkerState.ACTIVE)
    active_result = run_action(
        RegisterWorkerInput(worker_id="worker-1", queues=["agent"]),
        lease_duration_seconds=30,
    )
    assert active_result.worker.state.value == "active"
    assert active_result.claimed_job is not None
    assert active_result.claimed_job.id == "job-1"

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT state, worker_id FROM jobs WHERE id = :job_id"),
            {"job_id": "job-1"},
        ).one()

    assert row.state == "running"
    assert row.worker_id == "worker-1"


def test_draining_worker_does_not_claim_new_jobs(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 22, 20, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-1",
                queue="agent",
                command="echo one",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="queued",
            )
        )

    register_action = RegisterWorkerAction(
        SessionManager(session_factory),
        WorkerService(),
        clock=lambda: now,
    )
    set_state_action = SetWorkerStateAction(
        SessionManager(session_factory),
        WorkerService(),
        clock=lambda: now,
    )
    run_action = RunWorkerAction(
        SessionManager(session_factory),
        WorkerService(JobService(), QueueService()),
        job_service=JobService(),
        attempt_service=AttemptService(JobService()),
        execution_service=CommandExecutionService(),
        log_root=tmp_path / "logs",
        metrics=MetricsService(tmp_path / "metrics.json"),
        clock=lambda: now,
    )

    register_action(RegisterWorkerInput(worker_id="worker-1", queues=["agent"]))
    set_state_action("worker-1", WorkerState.DRAINING)

    draining_result = run_action(
        RegisterWorkerInput(worker_id="worker-1", queues=["agent"]),
        lease_duration_seconds=30,
    )
    assert draining_result.worker.state.value == "draining"
    assert draining_result.claimed_job is None

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT state, worker_id FROM jobs WHERE id = :job_id"),
            {"job_id": "job-1"},
        ).one()

    assert row.state == "queued"
    assert row.worker_id is None
