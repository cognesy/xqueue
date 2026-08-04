from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from xqueue.adapters.sqlite.database import create_session_factory, create_sqlite_engine
from xqueue.adapters.sqlite.models import Base, JobModel, WorkerModel
from xqueue.adapters.sqlite.session import SessionManager
from xqueue.core.datetimes import ensure_utc
from xqueue.workers.models import WorkerState
from xqueue.workers.store import WorkerService


def test_renew_job_lease_updates_running_job_owned_by_worker(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session_manager = SessionManager(session_factory)
    now = datetime(2026, 3, 22, 22, 30, tzinfo=UTC)

    with session_manager.transaction() as session:
        session.add(WorkerModel(id="worker-1", state="active", queues=["agent"], heartbeat_at=now, started_at=now))
        session.add(
            JobModel(
                id="job-1",
                queue="agent",
                command="sleep 1",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="running",
                worker_id="worker-1",
                lease_expires_at=now + timedelta(seconds=5),
            )
        )

    renewed_until = now + timedelta(seconds=20)
    with session_manager.transaction() as session:
        renewed = WorkerService().renew_job_lease(
            session,
            job_id="job-1",
            worker_id="worker-1",
            lease_expires_at=renewed_until,
        )

    assert renewed is True

    with session_manager.session() as session:
        job = session.get(JobModel, "job-1")

    assert job is not None
    assert job.lease_expires_at is not None
    assert ensure_utc(job.lease_expires_at) >= renewed_until


def test_renew_job_lease_rejects_wrong_worker_owner(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session_manager = SessionManager(session_factory)
    now = datetime(2026, 3, 22, 22, 35, tzinfo=UTC)
    original_lease = now + timedelta(seconds=5)

    with session_manager.transaction() as session:
        session.add(WorkerModel(id="worker-1", state="active", queues=["agent"], heartbeat_at=now, started_at=now))
        session.add(WorkerModel(id="worker-2", state="active", queues=["agent"], heartbeat_at=now, started_at=now))
        session.add(
            JobModel(
                id="job-1",
                queue="agent",
                command="sleep 1",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="running",
                worker_id="worker-1",
                lease_expires_at=original_lease,
            )
        )

    with session_manager.transaction() as session:
        renewed = WorkerService().renew_job_lease(
            session,
            job_id="job-1",
            worker_id="worker-2",
            lease_expires_at=now + timedelta(seconds=20),
        )

    assert renewed is False

    with session_manager.session() as session:
        job = session.get(JobModel, "job-1")

    assert job is not None
    assert job.lease_expires_at is not None
    assert ensure_utc(job.lease_expires_at) == original_lease


def test_set_worker_state_can_preserve_existing_heartbeat(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session_manager = SessionManager(session_factory)
    now = datetime(2026, 3, 22, 22, 40, tzinfo=UTC)
    original_heartbeat = now - timedelta(minutes=5)

    with session_manager.transaction() as session:
        session.add(
            WorkerModel(
                id="worker-1",
                state="active",
                queues=["agent"],
                heartbeat_at=original_heartbeat,
                started_at=now - timedelta(minutes=10),
            )
        )

    with session_manager.transaction() as session:
        worker = WorkerService().set_worker_state(
            session,
            worker_id="worker-1",
            state=WorkerState.PAUSED,
            now=now,
            touch_heartbeat=False,
        )

    assert worker.state == WorkerState.PAUSED
    assert worker.heartbeat_at == original_heartbeat

    with session_manager.session() as session:
        model = session.get(WorkerModel, "worker-1")

    assert model is not None
    assert ensure_utc(model.heartbeat_at) == original_heartbeat
