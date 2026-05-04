from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text

from xqueue_libs.actions.jobs import CancelJobAction, DeleteJobAction, RetryJobAction
from xqueue_libs.domain.errors import ConflictError
from xqueue_libs.actions.workers import RunWorkerAction
from xqueue_libs.domain.models import RegisterWorkerInput
from xqueue_libs.infra.database import create_session_factory, create_sqlite_engine
from xqueue_libs.infra.models import AttemptModel, Base, JobModel
from xqueue_libs.services.attempts import AttemptService
from xqueue_libs.services.database import SessionManager
from xqueue_libs.services.execution import CommandExecutionService
from xqueue_libs.services.job_logs import JobLogService
from xqueue_libs.services.jobs import JobService
from xqueue_libs.services.workers import WorkerService


def _build_run_worker_action(*, session_factory, log_root: Path, clock) -> RunWorkerAction:
    job_service = JobService()
    return RunWorkerAction(
        SessionManager(session_factory),
        WorkerService(job_service),
        job_service=job_service,
        attempt_service=AttemptService(job_service),
        execution_service=CommandExecutionService(),
        log_root=log_root,
        default_timeout_seconds=30,
        cancel_grace_period_seconds=1,
        retry_delay_seconds=5,
        clock=clock,
    )


def test_cancel_job_action_cancels_queued_job(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 20, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-queued",
                queue="agent",
                command="echo queued",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="queued",
            )
        )

    action = CancelJobAction(SessionManager(session_factory), JobService(), clock=lambda: now)
    result = action("job-queued")

    assert result.item.state.value == "canceled"
    assert result.item.cancel_requested_at == now

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT state, cancel_requested_at, last_error FROM jobs WHERE id = :job_id"),
            {"job_id": "job-queued"},
        ).one()

    assert row.state == "canceled"
    assert row.cancel_requested_at is not None
    assert row.last_error == "canceled"


def test_cancel_job_action_requests_running_job_cancellation_and_worker_enforces_it(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session_manager = SessionManager(session_factory)
    now = datetime(2026, 3, 22, 21, 25, tzinfo=UTC)

    with session_manager.transaction() as session:
        session.add(
            JobModel(
                id="job-running",
                queue="agent",
                command="sleep 30",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="queued",
                max_attempts=1,
            )
        )

    worker_action = _build_run_worker_action(
        session_factory=session_factory,
        log_root=tmp_path / "logs",
        clock=lambda: now,
    )
    cancel_action = CancelJobAction(
        SessionManager(session_factory),
        JobService(),
        clock=lambda: now,
    )
    container: dict[str, object] = {}

    def run_worker() -> None:
        container["result"] = worker_action(
            RegisterWorkerInput(worker_id="worker-1", queues=["agent"]),
            lease_duration_seconds=30,
            execute_claimed=True,
        )

    worker_thread = threading.Thread(target=run_worker)
    worker_thread.start()

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with session_manager.session() as session:
            job = JobService().get_job(session, job_id="job-running")
        if job.state.value == "running":
            break
        time.sleep(0.05)
    else:
        raise AssertionError("job never entered running state")

    cancel_result = cancel_action("job-running")
    assert cancel_result.item.id == "job-running"
    assert cancel_result.item.cancel_requested_at == now

    worker_thread.join(timeout=5)
    assert not worker_thread.is_alive()

    final_result = container["result"]
    assert final_result.item.claimed_job is not None
    assert final_result.item.claimed_job.state.value == "canceled"
    assert final_result.item.claimed_job.attempts[0].state.value == "canceled"
    assert final_result.item.claimed_job.attempts[0].cancellation_reason == "operator_requested"

    with engine.connect() as connection:
        job_row = connection.execute(
            text("SELECT state, worker_id, lease_expires_at, last_error FROM jobs WHERE id = :job_id"),
            {"job_id": "job-running"},
        ).one()
        attempt_row = connection.execute(
            text("SELECT state, cancellation_reason FROM attempts WHERE job_id = :job_id"),
            {"job_id": "job-running"},
        ).one()

    assert job_row.state == "canceled"
    assert job_row.worker_id is None
    assert job_row.lease_expires_at is None
    assert job_row.last_error == "canceled"
    assert attempt_row.state == "canceled"
    assert attempt_row.cancellation_reason == "operator_requested"


def test_retry_job_action_requeues_terminal_job_without_erasing_attempts(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 30, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-failed",
                queue="agent",
                command="echo failed",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="failed",
                attempt_count=1,
                last_exit_code=1,
                last_error="command exited with code 1",
                max_attempts=1,
            )
        )
        session.add(
            AttemptModel(
                job_id="job-failed",
                attempt_number=1,
                state="failed",
                started_at=now,
                finished_at=now,
                exit_code=1,
                error="command exited with code 1",
                stdout_path=str(tmp_path / "attempt.stdout.log"),
                stderr_path=str(tmp_path / "attempt.stderr.log"),
            )
        )

    action = RetryJobAction(SessionManager(session_factory), JobService(), clock=lambda: now)
    result = action("job-failed")

    assert result.item.state.value == "queued"
    assert result.item.attempt_count == 1
    assert len(result.item.attempts) == 1
    assert result.item.last_error is None
    assert result.item.last_exit_code is None

    with engine.connect() as connection:
        job_row = connection.execute(
            text("SELECT state, attempt_count, last_error, last_exit_code FROM jobs WHERE id = :job_id"),
            {"job_id": "job-failed"},
        ).one()
        attempts = connection.execute(
            text("SELECT COUNT(*) AS count FROM attempts WHERE job_id = :job_id"),
            {"job_id": "job-failed"},
        ).one()

    assert job_row.state == "queued"
    assert job_row.attempt_count == 1
    assert job_row.last_error is None
    assert job_row.last_exit_code is None
    assert attempts.count == 1


def test_delete_job_action_removes_non_running_job_history_and_logs(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 35, tzinfo=UTC)
    stdout_path = tmp_path / "logs" / "job-delete.stdout.log"
    stderr_path = tmp_path / "logs" / "job-delete.stderr.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text("stdout\n")
    stderr_path.write_text("stderr\n")

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-delete",
                queue="agent",
                command="echo delete",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="failed",
                attempt_count=1,
                last_error="boom",
            )
        )
        session.add(
            AttemptModel(
                job_id="job-delete",
                attempt_number=1,
                state="failed",
                started_at=now,
                finished_at=now,
                exit_code=1,
                error="boom",
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
            )
        )

    action = DeleteJobAction(SessionManager(session_factory), JobService(), JobLogService())
    result = action("job-delete")

    assert result.item.job_id == "job-delete"
    assert result.item.deleted_state.value == "failed"
    assert result.item.deleted_attempt_count == 1
    assert sorted(result.item.deleted_log_paths) == sorted([str(stdout_path), str(stderr_path)])
    assert not stdout_path.exists()
    assert not stderr_path.exists()

    with engine.connect() as connection:
        job_count = connection.execute(text("SELECT COUNT(*) AS count FROM jobs WHERE id = :job_id"), {"job_id": "job-delete"}).one()
        attempt_count = connection.execute(
            text("SELECT COUNT(*) AS count FROM attempts WHERE job_id = :job_id"),
            {"job_id": "job-delete"},
        ).one()

    assert job_count.count == 0
    assert attempt_count.count == 0


def test_delete_job_action_rejects_running_job(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 36, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-running-delete",
                queue="agent",
                command="sleep 10",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="running",
            )
        )

    action = DeleteJobAction(SessionManager(session_factory), JobService(), JobLogService())

    with pytest.raises(ConflictError) as exc_info:
        action("job-running-delete")

    assert exc_info.value.details == {"job_id": "job-running-delete", "state": "running"}


def test_retry_job_action_requeues_timed_out_job(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 37, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-timed-out",
                queue="agent",
                command="sleep 999",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="timed_out",
                attempt_count=1,
                last_error="timed out",
                max_attempts=1,
            )
        )
        session.add(
            AttemptModel(
                job_id="job-timed-out",
                attempt_number=1,
                state="timed_out",
                started_at=now,
                finished_at=now,
                error="timed out",
            )
        )

    action = RetryJobAction(SessionManager(session_factory), JobService(), clock=lambda: now)
    result = action("job-timed-out")

    assert result.item.state.value == "queued"
    assert result.item.last_error is None
    assert result.item.last_exit_code is None
    assert result.item.cancel_requested_at is None
    assert len(result.item.attempts) == 1


def test_retry_job_action_requeues_dead_job(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 38, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-dead",
                queue="agent",
                command="echo dead",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="dead",
                attempt_count=3,
                last_error="exhausted",
                max_attempts=3,
            )
        )

    action = RetryJobAction(SessionManager(session_factory), JobService(), clock=lambda: now)
    result = action("job-dead")

    assert result.item.state.value == "queued"
    assert result.item.last_error is None


def test_retry_job_action_rejects_non_terminal_states(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 21, 39, tzinfo=UTC)

    for state in ("running", "queued", "retry_scheduled", "succeeded"):
        with SessionManager(session_factory).transaction() as session:
            session.add(
                JobModel(
                    id=f"job-{state}",
                    queue="agent",
                    command="echo x",
                    shell=True,
                    priority=10,
                    created_at=now,
                    available_at=now,
                    state=state,
                )
            )

        from xqueue_libs.domain.errors import ConflictError as _ConflictError
        action = RetryJobAction(SessionManager(session_factory), JobService(), clock=lambda: now)
        with pytest.raises(_ConflictError):
            action(f"job-{state}")
