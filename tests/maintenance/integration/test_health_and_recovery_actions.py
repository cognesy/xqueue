from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from xqueue.adapters.sqlite.database import create_session_factory, create_sqlite_engine
from xqueue.adapters.sqlite.models import AttemptModel, Base, JobModel, QueueModel, WorkerModel
from xqueue.adapters.sqlite.session import SessionManager
from xqueue.jobs.models import JobState
from xqueue.jobs.store import JobService
from xqueue.maintenance.actions import DoctorAction, HealthAction
from xqueue.maintenance.database import DatabaseMaintenanceService
from xqueue.maintenance.health import HealthService
from xqueue.maintenance.recovery import RECOVERY_ERROR, RecoveryService
from xqueue.maintenance.recovery_actions import RecoverStaleLeasesAction


def test_recover_stale_leases_requeues_job_and_records_event(tmp_path: Path) -> None:
    database_path = tmp_path / "recovery.db"
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 23, 0, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            WorkerModel(
                id="worker-1", state="active", queues=["alpha"], heartbeat_at=now - timedelta(minutes=2), started_at=now
            )
        )
        session.add(
            JobModel(
                id="job-stale",
                queue="alpha",
                command="sleep 60",
                shell=True,
                priority=10,
                created_at=now - timedelta(minutes=1),
                available_at=now - timedelta(minutes=1),
                state="running",
                lease_expires_at=now - timedelta(seconds=30),
                worker_id="worker-1",
                attempt_count=1,
                max_attempts=3,
            )
        )
        session.add(
            AttemptModel(
                job_id="job-stale",
                attempt_number=1,
                worker_id="worker-1",
                state="running",
                started_at=now - timedelta(minutes=1),
                stdout_path="/tmp/job-stale.stdout",
                stderr_path="/tmp/job-stale.stderr",
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
    assert result.items[0].job_id == "job-stale"
    assert result.items[0].new_state == JobState.RETRY_SCHEDULED
    assert result.items[0].available_at == now + timedelta(seconds=15)

    with SessionManager(session_factory).session() as session:
        job = JobService().get_job(session, job_id="job-stale")

    assert job.state == JobState.RETRY_SCHEDULED
    assert job.worker_id is None
    assert job.lease_expires_at is None
    assert job.last_error == RECOVERY_ERROR
    assert job.attempts[0].state.value == "failed"
    assert job.attempts[0].finished_at == now
    assert job.attempts[0].error == RECOVERY_ERROR
    assert job.events[0].event_type == "job.recovered_stale_lease"
    assert job.events[0].payload == {
        "recovery_error": RECOVERY_ERROR,
        "previous_worker_id": "worker-1",
        "attempt_id": job.attempts[0].id,
        "new_state": "retry_scheduled",
    }


def test_recover_stale_leases_marks_job_failed_when_attempts_are_exhausted(tmp_path: Path) -> None:
    database_path = tmp_path / "recovery.db"
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 23, 5, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(WorkerModel(id="worker-2", state="active", queues=["alpha"], heartbeat_at=now, started_at=now))
        session.add(
            JobModel(
                id="job-final",
                queue="alpha",
                command="sleep 60",
                shell=True,
                priority=10,
                created_at=now - timedelta(minutes=1),
                available_at=now - timedelta(minutes=1),
                state="running",
                lease_expires_at=now - timedelta(seconds=45),
                worker_id="worker-2",
                attempt_count=1,
                max_attempts=1,
            )
        )
        session.add(
            AttemptModel(
                job_id="job-final",
                attempt_number=1,
                worker_id="worker-2",
                state="running",
                started_at=now - timedelta(minutes=1),
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
    assert result.items[0].new_state == JobState.FAILED
    assert result.items[0].available_at is None

    with SessionManager(session_factory).session() as session:
        job = JobService().get_job(session, job_id="job-final")

    assert job.state == JobState.FAILED
    assert job.last_error == RECOVERY_ERROR


def test_health_and_doctor_surface_paused_queues_stale_leases_and_stale_workers(tmp_path: Path) -> None:
    database_path = tmp_path / "ops.db"
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 23, 10, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(QueueModel(name="alpha", state="paused", updated_at=now, paused_at=now))
        session.add(
            WorkerModel(
                id="worker-stale",
                state="active",
                queues=["alpha"],
                heartbeat_at=now - timedelta(minutes=5),
                started_at=now - timedelta(minutes=10),
            )
        )
        session.add(
            JobModel(
                id="job-stale-health",
                queue="alpha",
                command="sleep 60",
                shell=True,
                priority=10,
                created_at=now - timedelta(minutes=1),
                available_at=now - timedelta(minutes=1),
                state="running",
                lease_expires_at=now - timedelta(seconds=5),
                worker_id="worker-stale",
                attempt_count=1,
                max_attempts=2,
            )
        )

    database_service = DatabaseMaintenanceService(engine, database_path=database_path)
    health_action = HealthAction(
        SessionManager(session_factory),
        HealthService(),
        database_service,
        clock=lambda: now,
    )
    doctor_action = DoctorAction(
        SessionManager(session_factory),
        HealthService(),
        database_service,
        clock=lambda: now,
    )

    health_result = health_action()
    doctor_result = doctor_action()

    assert health_result.status.value == "warn"
    assert health_result.database_status.value == "ok"
    assert health_result.paused_queues == ["alpha"]
    assert [item.job_id for item in health_result.stale_leases] == ["job-stale-health"]
    assert [item.id for item in health_result.stale_workers] == ["worker-stale"]

    checks = {check.name: check for check in doctor_result.checks}
    assert doctor_result.status.value == "warn"
    assert checks["database.integrity"].status.value == "ok"
    assert checks["queues.paused"].status.value == "warn"
    assert checks["leases.stale"].details["job_ids"] == ["job-stale-health"]
    assert checks["workers.heartbeat"].details["worker_ids"] == ["worker-stale"]
