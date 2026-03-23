from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.actions.jobs import ListJobsAction, ShowJobAction, TailJobLogsAction
from libs.domain.errors import NotFoundError
from libs.domain.models import AttemptLogStream, JobListFilters, JobListSort
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.infra.models import AttemptModel, Base, JobModel
from libs.services.database import SessionManager
from libs.services.job_logs import JobLogService
from libs.services.jobs import JobService


def test_list_jobs_action_filters_and_sorts_jobs(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 20, 15, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add_all(
            [
                JobModel(
                    id="job-1",
                    queue="agent",
                    command="echo one",
                    shell=True,
                    priority=50,
                    created_at=now,
                    available_at=now + timedelta(seconds=10),
                    state="queued",
                ),
                JobModel(
                    id="job-2",
                    queue="agent",
                    command="echo two",
                    shell=True,
                    priority=40,
                    created_at=now + timedelta(seconds=1),
                    available_at=now + timedelta(seconds=3),
                    state="queued",
                ),
                JobModel(
                    id="job-3",
                    queue="agent",
                    command="echo three",
                    shell=True,
                    priority=30,
                    created_at=now + timedelta(seconds=2),
                    available_at=now + timedelta(seconds=1),
                    state="queued",
                ),
                JobModel(
                    id="job-4",
                    queue="default",
                    command="echo four",
                    shell=True,
                    priority=20,
                    created_at=now + timedelta(seconds=3),
                    available_at=now + timedelta(seconds=2),
                    state="queued",
                ),
            ]
        )

    action = ListJobsAction(SessionManager(session_factory), JobService())
    result = action(
        JobListFilters(
            queue="agent",
            state="queued",
            created_after=now + timedelta(milliseconds=500),
            available_before=now + timedelta(seconds=4),
            sort=JobListSort.AVAILABLE_ASC,
            limit=10,
        )
    )

    assert [item.id for item in result.items] == ["job-3", "job-2"]
    assert [item.state.value for item in result.items] == ["queued", "queued"]


def test_show_job_action_returns_detail_with_attempts(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 20, 20, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-123",
                queue="agent",
                command="echo detail",
                shell=True,
                cwd="/tmp/work",
                env={"FOO": "bar"},
                priority=25,
                timeout_seconds=60,
                max_attempts=2,
                created_at=now,
                available_at=now,
                state="failed",
                attempt_count=1,
                last_exit_code=1,
                last_error="boom",
                created_by="tester",
            )
        )
        session.add(
            AttemptModel(
                job_id="job-123",
                attempt_number=1,
                state="failed",
                started_at=now,
                finished_at=now + timedelta(seconds=5),
                exit_code=1,
                error="boom",
                stdout_path="/tmp/stdout.log",
                stderr_path="/tmp/stderr.log",
            )
        )

    action = ShowJobAction(SessionManager(session_factory), JobService())
    result = action("job-123")

    assert result.item.id == "job-123"
    assert result.item.last_error == "boom"
    assert len(result.item.attempts) == 1
    assert result.item.attempts[0].stderr_path == "/tmp/stderr.log"


def test_show_job_action_raises_not_found_for_missing_job(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    action = ShowJobAction(SessionManager(session_factory), JobService())

    with pytest.raises(NotFoundError) as exc_info:
        action("missing-job")

    assert exc_info.value.details == {"job_id": "missing-job"}


def test_tail_job_logs_action_returns_latest_attempt_stderr(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 3, 22, 20, 25, tzinfo=UTC)
    stderr_path = tmp_path / "logs" / "job-tail.stderr.log"
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.write_text("first\nsecond\nthird\n")

    with SessionManager(session_factory).transaction() as session:
        session.add(
            JobModel(
                id="job-tail",
                queue="agent",
                command="echo tail",
                shell=True,
                priority=25,
                created_at=now,
                available_at=now,
                state="failed",
                attempt_count=1,
            )
        )
        session.add(
            AttemptModel(
                job_id="job-tail",
                attempt_number=1,
                state="failed",
                started_at=now,
                finished_at=now + timedelta(seconds=1),
                exit_code=1,
                error="boom",
                stderr_path=str(stderr_path),
            )
        )

    action = TailJobLogsAction(SessionManager(session_factory), JobService(), JobLogService())
    result = action("job-tail", stream=AttemptLogStream.STDERR, lines=2)

    assert result.item.job_id == "job-tail"
    assert result.item.path == str(stderr_path)
    assert result.item.lines == ["second", "third"]
    assert result.item.truncated is True
