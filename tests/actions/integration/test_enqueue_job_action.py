from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from xqueue_libs.actions.jobs import EnqueueJobAction
from xqueue_libs.domain.models import EnqueueJobInput
from xqueue_libs.infra.database import create_session_factory, create_sqlite_engine
from xqueue_libs.infra.models import Base
from xqueue_libs.services.database import SessionManager
from xqueue_libs.services.jobs import JobService


def test_enqueue_job_action_persists_queued_job(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    action = EnqueueJobAction(
        SessionManager(session_factory),
        JobService(),
        clock=lambda: datetime(2026, 3, 22, 20, 0, tzinfo=UTC),
        id_factory=lambda: "job-123",
    )

    result = action(
        EnqueueJobInput(
            queue="agent",
            command="echo hi",
            cwd="/tmp",
            priority=10,
            timeout_seconds=30,
            max_attempts=3,
            created_by="tester",
        )
    )

    assert result.ok is True
    assert result.item.id == "job-123"
    assert result.item.state.value == "queued"

    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT queue, command, state, cwd, priority, timeout_seconds, "
                "max_attempts, created_by FROM jobs WHERE id = :job_id"
            ),
            {"job_id": "job-123"},
        ).one()

    assert row.queue == "agent"
    assert row.command == "echo hi"
    assert row.state == "queued"
    assert row.cwd == "/tmp"
    assert row.priority == 10
    assert row.timeout_seconds == 30
    assert row.max_attempts == 3
    assert row.created_by == "tester"

    with engine.connect() as connection:
        event_row = connection.execute(
            text("SELECT event_type, job_id FROM events WHERE job_id = :job_id"),
            {"job_id": "job-123"},
        ).one()
    assert event_row.event_type == "job.enqueued"
    assert event_row.job_id == "job-123"
