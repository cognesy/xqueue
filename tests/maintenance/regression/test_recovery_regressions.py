from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from xqueue.adapters.sqlite.database import create_session_factory, create_sqlite_engine
from xqueue.adapters.sqlite.models import Base, JobModel, WorkerModel
from xqueue.adapters.sqlite.session import SessionManager
from xqueue.jobs.models import JobState
from xqueue.jobs.store import JobService
from xqueue.maintenance.recovery import RECOVERY_ERROR, RecoveryService
from xqueue.maintenance.recovery_actions import RecoverStaleLeasesAction


def test_recover_stale_lease_without_running_attempt_keeps_history_visible(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "recovery.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 23, 30, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            WorkerModel(
                id="worker-1",
                state="active",
                queues=["alpha"],
                heartbeat_at=now - timedelta(minutes=5),
                started_at=now - timedelta(minutes=10),
            )
        )
        session.add(
            JobModel(
                id="job-stale-no-attempt",
                queue="alpha",
                command="sleep 60",
                shell=True,
                priority=10,
                created_at=now - timedelta(minutes=1),
                available_at=now - timedelta(minutes=1),
                state="running",
                lease_expires_at=now - timedelta(seconds=20),
                worker_id="worker-1",
                attempt_count=0,
                max_attempts=1,
            )
        )

    action = RecoverStaleLeasesAction(
        SessionManager(session_factory),
        RecoveryService(),
        retry_delay_seconds=15,
        clock=lambda: now,
    )
    result = action()

    assert result.recovered_count == 1
    assert result.items[0].job_id == "job-stale-no-attempt"
    assert result.items[0].attempt_id is None
    assert result.items[0].new_state == JobState.RETRY_SCHEDULED

    with SessionManager(session_factory).session() as session:
        job = JobService().get_job(session, job_id="job-stale-no-attempt")

    assert job.state == JobState.RETRY_SCHEDULED
    assert job.attempts == []
    assert job.last_error == RECOVERY_ERROR
    assert len(job.events) == 1
    assert job.events[0].event_type == "job.recovered_stale_lease"
    assert job.events[0].payload == {
        "recovery_error": RECOVERY_ERROR,
        "previous_worker_id": "worker-1",
        "attempt_id": None,
        "new_state": "retry_scheduled",
    }
