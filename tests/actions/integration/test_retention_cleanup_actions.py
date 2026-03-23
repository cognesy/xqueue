from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from libs.actions.operations import CleanupRetentionAction
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.infra.models import AttemptModel, Base, EventModel, JobModel
from libs.services.database import SessionManager
from libs.services.job_logs import JobLogService
from libs.services.retention import RetentionCleanupService


def test_cleanup_retention_action_prunes_only_old_terminal_log_artifacts(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "queue.db")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session_manager = SessionManager(session_factory)
    now = datetime(2026, 3, 22, 23, 0, tzinfo=UTC)
    old_stdout = tmp_path / "logs" / "old.stdout.log"
    old_stderr = tmp_path / "logs" / "old.stderr.log"
    recent_stdout = tmp_path / "logs" / "recent.stdout.log"
    old_stdout.parent.mkdir(parents=True, exist_ok=True)
    old_stdout.write_text("old\n")
    old_stderr.write_text("old\n")
    recent_stdout.write_text("recent\n")

    with session_manager.transaction() as session:
        session.add_all(
            [
                JobModel(
                    id="job-old",
                    queue="agent",
                    command="echo old",
                    shell=True,
                    priority=10,
                    created_at=now - timedelta(days=3),
                    available_at=now - timedelta(days=3),
                    state="failed",
                    attempt_count=1,
                    last_exit_code=1,
                    last_error="boom",
                ),
                JobModel(
                    id="job-recent",
                    queue="agent",
                    command="echo recent",
                    shell=True,
                    priority=10,
                    created_at=now - timedelta(hours=2),
                    available_at=now - timedelta(hours=2),
                    state="failed",
                    attempt_count=1,
                    last_exit_code=1,
                    last_error="boom",
                ),
            ]
        )
        session.add_all(
            [
                AttemptModel(
                    job_id="job-old",
                    attempt_number=1,
                    state="failed",
                    started_at=now - timedelta(days=3),
                    finished_at=now - timedelta(days=3) + timedelta(minutes=1),
                    exit_code=1,
                    error="boom",
                    stdout_path=str(old_stdout),
                    stderr_path=str(old_stderr),
                ),
                AttemptModel(
                    job_id="job-recent",
                    attempt_number=1,
                    state="failed",
                    started_at=now - timedelta(hours=2),
                    finished_at=now - timedelta(hours=2) + timedelta(minutes=1),
                    exit_code=1,
                    error="boom",
                    stdout_path=str(recent_stdout),
                ),
            ]
        )
        session.add(
            EventModel(
                event_type="job.recovered_stale_lease",
                created_at=now - timedelta(days=3),
                payload={"job_id": "job-old"},
                job_id="job-old",
                attempt_id=1,
            )
        )

    action = CleanupRetentionAction(
        session_manager,
        RetentionCleanupService(),
        JobLogService(),
        clock=lambda: now,
    )
    result = action(
        older_than_hours=24,
        prune_attempts=False,
        prune_events=False,
        prune_logs=True,
    )

    assert result.item.deleted_attempt_count == 0
    assert result.item.deleted_event_count == 0
    assert result.item.deleted_log_count == 2
    assert sorted(Path(path).name for path in result.item.deleted_log_paths) == ["old.stderr.log", "old.stdout.log"]
    assert not old_stdout.exists()
    assert not old_stderr.exists()
    assert recent_stdout.exists()

    with session_manager.session() as session:
        attempts = session.execute(select(AttemptModel).order_by(AttemptModel.job_id.asc())).scalars().all()

    assert len(attempts) == 2
    old_attempt = next(item for item in attempts if item.job_id == "job-old")
    recent_attempt = next(item for item in attempts if item.job_id == "job-recent")
    assert old_attempt.stdout_path is None
    assert old_attempt.stderr_path is None
    assert recent_attempt.stdout_path == str(recent_stdout)
