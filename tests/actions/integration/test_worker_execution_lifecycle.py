from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from libs.actions.workers import RunWorkerAction, RunWorkerLoopAction
from libs.domain.models import RegisterWorkerInput
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.infra.models import Base, JobModel
from libs.services.database import SessionManager
from libs.services.attempts import AttemptService
from libs.services.execution import CommandExecutionService
from libs.services.jobs import JobService
from libs.services.recovery import RecoveryService
from libs.services.workers import WorkerService


def _build_action(
    *,
    session_factory,
    log_root: Path,
    clock,
    default_timeout_seconds: int = 30,
    cancel_grace_period_seconds: int = 1,
    retry_delay_seconds: int = 5,
) -> RunWorkerAction:
    job_service = JobService()
    return RunWorkerAction(
        SessionManager(session_factory),
        WorkerService(job_service),
        job_service=job_service,
        attempt_service=AttemptService(job_service),
        execution_service=CommandExecutionService(),
        log_root=log_root,
        default_timeout_seconds=default_timeout_seconds,
        cancel_grace_period_seconds=cancel_grace_period_seconds,
        retry_delay_seconds=retry_delay_seconds,
        clock=clock,
    )


def test_run_worker_action_executes_successful_job_and_records_attempt(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 5, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-success",
                queue="agent",
                command="printf 'success\\n'",
                shell=True,
                env={
                    "XPM_DISPATCH_RUN_ID": "dispatch-123",
                    "XPM_DEDUPE_KEY": "candidate-123",
                    "IGNORED_SECRET": "do-not-log",
                },
                priority=10,
                created_at=now,
                available_at=now,
                state="queued",
                max_attempts=1,
            )
        )

    action = _build_action(session_factory=session_factory, log_root=tmp_path / "logs", clock=lambda: now)
    result = action(
        RegisterWorkerInput(worker_id="worker-1", queues=["agent"]),
        lease_duration_seconds=30,
        execute_claimed=True,
    )

    assert result.item.claimed_job is not None
    assert result.item.claimed_job.state.value == "succeeded"
    assert len(result.item.claimed_job.attempts) == 1
    assert Path(result.item.claimed_job.attempts[0].stdout_path or "").read_text() == "success\n"

    with engine.connect() as connection:
        job_row = connection.execute(
            text("SELECT state, attempt_count, worker_id, last_exit_code FROM jobs WHERE id = :job_id"),
            {"job_id": "job-success"},
        ).one()
        attempt_row = connection.execute(
            text("SELECT state, exit_code, stdout_path, stderr_path FROM attempts WHERE job_id = :job_id"),
            {"job_id": "job-success"},
        ).one()

    assert job_row.state == "succeeded"
    assert job_row.attempt_count == 1
    assert job_row.worker_id is None
    assert job_row.last_exit_code == 0
    assert attempt_row.state == "succeeded"
    assert attempt_row.exit_code == 0
    assert Path(attempt_row.stdout_path).read_text() == "success\n"
    assert Path(attempt_row.stderr_path).read_text() == ""

    operation_log_path = Path(result.item.claimed_job.attempts[0].event_log_path or "")
    operation_events = [json.loads(line) for line in operation_log_path.read_text().splitlines()]
    assert [item["event"] for item in operation_events] == [
        "job.claimed",
        "job.started",
        "job.finished",
        "job.succeeded",
    ]
    assert all(item["timestamp"].endswith("Z") for item in operation_events)
    assert operation_events[-1]["outcome"] == "succeeded"
    assert operation_events[-1]["exit_code"] == 0
    assert operation_events[-1]["stdout_path"] == attempt_row.stdout_path
    assert operation_events[-1]["stderr_path"] == attempt_row.stderr_path
    assert operation_events[-1]["correlation"] == {
        "xpm_dedupe_key": "candidate-123",
        "xpm_dispatch_run_id": "dispatch-123",
    }
    assert "do-not-log" not in operation_log_path.read_text()

    with engine.connect() as connection:
        event_types = connection.execute(
            text("SELECT event_type FROM events WHERE job_id = :job_id ORDER BY id"),
            {"job_id": "job-success"},
        ).scalars().all()
    assert "job.started" in event_types
    assert "job.succeeded" in event_types


def test_run_worker_action_schedules_retry_then_succeeds_on_second_attempt(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    now = datetime(2026, 3, 22, 21, 10, tzinfo=UTC)

    command = "if [ -f success.flag ]; then printf 'second\\n'; exit 0; else touch success.flag; printf 'first\\n' >&2; exit 7; fi"

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-retry",
                queue="agent",
                command=command,
                shell=True,
                cwd=str(work_dir),
                priority=10,
                created_at=now,
                available_at=now,
                state="queued",
                max_attempts=2,
            )
        )

    first_action = _build_action(
        session_factory=session_factory,
        log_root=tmp_path / "logs",
        clock=lambda: now,
        retry_delay_seconds=3,
    )
    first_result = first_action(
        RegisterWorkerInput(worker_id="worker-1", queues=["agent"]),
        lease_duration_seconds=30,
        execute_claimed=True,
    )

    assert first_result.item.claimed_job is not None
    assert first_result.item.claimed_job.state.value == "retry_scheduled"
    assert len(first_result.item.claimed_job.attempts) == 1
    assert first_result.item.claimed_job.attempts[0].state.value == "failed"
    assert first_result.item.claimed_job.available_at is not None
    first_operation_log = Path(first_result.item.claimed_job.attempts[0].event_log_path or "")
    first_operation_events = [json.loads(line) for line in first_operation_log.read_text().splitlines()]
    assert first_operation_events[-1]["event"] == "job.retry_scheduled"
    assert first_operation_events[-1]["outcome"] == "retry_scheduled"

    second_action = _build_action(
        session_factory=session_factory,
        log_root=tmp_path / "logs",
        clock=lambda: first_result.item.claimed_job.available_at + timedelta(seconds=1),
        retry_delay_seconds=3,
    )
    second_result = second_action(
        RegisterWorkerInput(worker_id="worker-1", queues=["agent"]),
        lease_duration_seconds=30,
        execute_claimed=True,
    )

    assert second_result.item.claimed_job is not None
    assert second_result.item.claimed_job.state.value == "succeeded"
    assert len(second_result.item.claimed_job.attempts) == 2
    assert second_result.item.claimed_job.attempts[1].state.value == "succeeded"

    with engine.connect() as connection:
        job_row = connection.execute(
            text("SELECT state, attempt_count, last_exit_code, last_error FROM jobs WHERE id = :job_id"),
            {"job_id": "job-retry"},
        ).one()
        attempt_rows = connection.execute(
            text("SELECT attempt_number, state, exit_code FROM attempts WHERE job_id = :job_id ORDER BY attempt_number"),
            {"job_id": "job-retry"},
        ).all()

    assert job_row.state == "succeeded"
    assert job_row.attempt_count == 2
    assert job_row.last_exit_code == 0
    assert job_row.last_error is None
    assert [(row.attempt_number, row.state, row.exit_code) for row in attempt_rows] == [
        (1, "failed", 7),
        (2, "succeeded", 0),
    ]

    with engine.connect() as connection:
        event_types = connection.execute(
            text("SELECT event_type FROM events WHERE job_id = :job_id ORDER BY id"),
            {"job_id": "job-retry"},
        ).scalars().all()
    assert event_types.count("job.started") == 2
    assert "job.failed" in event_types
    assert "job.retry_scheduled" in event_types
    assert "job.succeeded" in event_types


def test_run_worker_action_marks_timeout_and_final_failure(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 15, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-timeout",
                queue="agent",
                command="sleep 2",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="queued",
                timeout_seconds=1,
                max_attempts=1,
            )
        )

    action = _build_action(
        session_factory=session_factory,
        log_root=tmp_path / "logs",
        clock=lambda: now,
        default_timeout_seconds=1,
        cancel_grace_period_seconds=1,
    )
    result = action(
        RegisterWorkerInput(worker_id="worker-1", queues=["agent"]),
        lease_duration_seconds=30,
        execute_claimed=True,
    )

    assert result.item.claimed_job is not None
    assert result.item.claimed_job.state.value == "failed"
    assert result.item.claimed_job.last_error == "timed out"
    assert result.item.claimed_job.attempts[0].state.value == "timed_out"

    with engine.connect() as connection:
        job_row = connection.execute(
            text("SELECT state, worker_id, lease_expires_at, last_error FROM jobs WHERE id = :job_id"),
            {"job_id": "job-timeout"},
        ).one()
        attempt_row = connection.execute(
            text("SELECT state, exit_code, error FROM attempts WHERE job_id = :job_id"),
            {"job_id": "job-timeout"},
        ).one()

    assert job_row.state == "failed"
    assert job_row.worker_id is None
    assert job_row.lease_expires_at is None
    assert job_row.last_error == "timed out"
    assert attempt_row.state == "timed_out"
    assert attempt_row.error == "timed out"

    with engine.connect() as connection:
        event_types = connection.execute(
            text("SELECT event_type FROM events WHERE job_id = :job_id ORDER BY id"),
            {"job_id": "job-timeout"},
        ).scalars().all()
    assert "job.started" in event_types
    assert "job.timed_out" in event_types


def test_run_worker_action_renews_job_lease_while_command_is_running(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session_manager = SessionManager(session_factory)
    seeded_at = datetime(2026, 3, 22, 21, 18, tzinfo=UTC)

    with session_manager.transaction() as session:
        session.add(
            JobModel(
                id="job-heartbeat",
                queue="agent",
                command="sleep 1.6",
                shell=True,
                priority=10,
                created_at=seeded_at,
                available_at=seeded_at,
                state="queued",
                timeout_seconds=10,
                max_attempts=1,
            )
        )

    action = _build_action(
        session_factory=session_factory,
        log_root=tmp_path / "logs",
        clock=lambda: datetime.now(UTC),
        default_timeout_seconds=10,
        cancel_grace_period_seconds=1,
    )
    container: dict[str, object] = {}

    def run_worker() -> None:
        container["result"] = action(
            RegisterWorkerInput(worker_id="worker-1", queues=["agent"]),
            lease_duration_seconds=1,
            execute_claimed=True,
        )

    worker_thread = threading.Thread(target=run_worker)
    worker_thread.start()

    initial_lease = None
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT state, lease_expires_at FROM jobs WHERE id = :job_id"),
                {"job_id": "job-heartbeat"},
            ).one()
        if row.state == "running" and row.lease_expires_at is not None:
            initial_lease = row.lease_expires_at
            break
        time.sleep(0.05)
    else:
        raise AssertionError("job never entered running state")

    time.sleep(1.1)

    with engine.connect() as connection:
        mid_run = connection.execute(
            text("SELECT state, lease_expires_at FROM jobs WHERE id = :job_id"),
            {"job_id": "job-heartbeat"},
        ).one()

    assert mid_run.state == "running"
    assert mid_run.lease_expires_at is not None
    assert mid_run.lease_expires_at > initial_lease

    with session_manager.session() as session:
        assert RecoveryService().list_stale_leases(session, now=datetime.now(UTC)) == []

    worker_thread.join(timeout=5)
    assert not worker_thread.is_alive()

    result = container["result"]
    assert result.item.claimed_job is not None
    assert result.item.claimed_job.state.value == "succeeded"


def test_run_worker_loop_action_executes_multiple_jobs_concurrently(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 25, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add_all(
            [
                JobModel(
                    id="job-concurrency-1",
                    queue="agent",
                    command="sleep 1; printf 'one\\n'",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state="queued",
                    max_attempts=1,
                ),
                JobModel(
                    id="job-concurrency-2",
                    queue="agent",
                    command="sleep 1; printf 'two\\n'",
                    shell=True,
                    priority=20,
                    created_at=now,
                    available_at=now,
                    state="queued",
                    max_attempts=1,
                ),
            ]
        )

    run_action = _build_action(
        session_factory=session_factory,
        log_root=tmp_path / "logs",
        clock=lambda: datetime.now(UTC),
    )
    loop_action = RunWorkerLoopAction(run_action)

    started = time.monotonic()
    result = loop_action(
        RegisterWorkerInput(worker_id="worker-1", queues=["agent"], concurrency=2),
        lease_duration_seconds=30,
        poll_interval_seconds=0.05,
        execute_claimed=True,
        max_polls=2,
    )
    elapsed = time.monotonic() - started

    assert result.item.worker.id == "worker-1"
    assert elapsed < 1.8

    with engine.connect() as connection:
        job_rows = connection.execute(
            text(
                "SELECT id, state, attempt_count FROM jobs WHERE id LIKE 'job-concurrency-%' ORDER BY id"
            )
        ).all()
        attempt_rows = connection.execute(
            text(
                "SELECT job_id, state FROM attempts WHERE job_id LIKE 'job-concurrency-%' ORDER BY job_id"
            )
        ).all()
        start_gap_seconds = connection.execute(
            text(
                "SELECT ABS((julianday(MAX(started_at)) - julianday(MIN(started_at))) * 86400.0) "
                "FROM attempts WHERE job_id LIKE 'job-concurrency-%'"
            )
        ).scalar_one()

    assert [(row.id, row.state, row.attempt_count) for row in job_rows] == [
        ("job-concurrency-1", "succeeded", 1),
        ("job-concurrency-2", "succeeded", 1),
    ]
    assert [row.state for row in attempt_rows] == ["succeeded", "succeeded"]
    assert start_gap_seconds is not None
    assert start_gap_seconds < 0.5
