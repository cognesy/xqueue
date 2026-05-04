from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from xqueue_libs.actions.workers import ClaimNextJobAction, RegisterWorkerAction, RunWorkerAction
from xqueue_libs.domain.models import RegisterWorkerInput
from xqueue_libs.infra.database import create_session_factory, create_sqlite_engine
from xqueue_libs.infra.models import Base, JobModel
from xqueue_libs.services.database import SessionManager
from xqueue_libs.services.workers import WorkerService


def test_register_worker_action_persists_active_worker(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    action = RegisterWorkerAction(
        SessionManager(session_factory),
        WorkerService(),
        clock=lambda: datetime(2026, 3, 22, 20, 45, tzinfo=UTC),
    )

    result = action(
        RegisterWorkerInput(
            worker_id="worker-1",
            queues=["agent"],
            concurrency=2,
            hostname="test-host",
            process_id=1234,
        )
    )

    assert result.item.id == "worker-1"
    assert result.item.state.value == "active"
    assert result.item.queues == ["agent"]

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT state, concurrency, hostname, process_id FROM workers WHERE id = :worker_id"),
            {"worker_id": "worker-1"},
        ).one()

    assert row.state == "active"
    assert row.concurrency == 2
    assert row.hostname == "test-host"
    assert row.process_id == 1234


def test_run_worker_action_claims_runnable_job(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 20, 50, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-1",
                queue="agent",
                command="echo hi",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="queued",
            )
        )

    action = RunWorkerAction(
        SessionManager(session_factory),
        WorkerService(),
        clock=lambda: now,
    )

    result = action(
        RegisterWorkerInput(
            worker_id="worker-1",
            queues=["agent"],
            concurrency=1,
            hostname="test-host",
            process_id=5678,
        ),
        lease_duration_seconds=45,
    )

    assert result.item.worker.id == "worker-1"
    assert result.item.claimed_job is not None
    assert result.item.claimed_job.id == "job-1"
    assert result.item.claimed_job.state.value == "running"

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT state, worker_id, lease_expires_at FROM jobs WHERE id = :job_id"),
            {"job_id": "job-1"},
        ).one()

    assert row.state == "running"
    assert row.worker_id == "worker-1"
    assert row.lease_expires_at is not None


def test_competing_claim_actions_only_claim_one_job(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 20, 55, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-1",
                queue="agent",
                command="echo hi",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="queued",
            )
        )

    register = RegisterWorkerAction(
        SessionManager(session_factory),
        WorkerService(),
        clock=lambda: now,
    )
    register(RegisterWorkerInput(worker_id="worker-a", queues=["agent"]))
    register(RegisterWorkerInput(worker_id="worker-b", queues=["agent"]))

    barrier = threading.Barrier(2)
    claimed_ids: list[str | None] = []
    lock = threading.Lock()

    def claim(worker_id: str) -> None:
        action = ClaimNextJobAction(
            SessionManager(session_factory),
            WorkerService(),
            clock=lambda: now + timedelta(seconds=1),
        )
        barrier.wait()
        result = action(worker_id=worker_id, queues=["agent"], lease_duration_seconds=30)
        claimed_job = result.item
        claimed_id = None if claimed_job is None else claimed_job.id
        with lock:
            claimed_ids.append(claimed_id)

    thread_a = threading.Thread(target=claim, args=("worker-a",))
    thread_b = threading.Thread(target=claim, args=("worker-b",))
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    assert claimed_ids.count("job-1") == 1
    assert claimed_ids.count(None) == 1

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT state, worker_id FROM jobs WHERE id = :job_id"),
            {"job_id": "job-1"},
        ).one()

    assert row.state == "running"
    assert row.worker_id in {"worker-a", "worker-b"}
