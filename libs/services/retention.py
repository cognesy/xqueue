"""Explicit retention cleanup services."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from libs.domain.models import JobState, RetentionCleanupResult
from libs.infra.models import AttemptModel, EventModel, JobModel


TERMINAL_JOB_STATES = (
    JobState.SUCCEEDED.value,
    JobState.FAILED.value,
    JobState.CANCELED.value,
)


class RetentionCleanupService:
    """Prune old attempt history, events, and log references explicitly."""

    def cleanup(
        self,
        session: Session,
        *,
        cutoff_at: datetime,
        prune_attempts: bool,
        prune_events: bool,
        prune_logs: bool,
    ) -> RetentionCleanupResult:
        deleted_attempt_count = 0
        deleted_event_count = 0
        deleted_log_paths: list[str] = []

        attempts = self._list_prunable_attempts(session, cutoff_at=cutoff_at)
        attempts_by_id = {attempt.id: attempt for attempt in attempts if attempt.id is not None}
        attempt_ids = list(attempts_by_id)

        if prune_attempts and attempt_ids:
            deleted_log_paths.extend(self._collect_attempt_log_paths(attempts_by_id.values()))
            deleted_event_count += self._delete_attempt_events(session, attempt_ids=attempt_ids)
            session.flush()
            for attempt in attempts_by_id.values():
                session.delete(attempt)
                deleted_attempt_count += 1
        elif prune_logs and attempt_ids:
            for attempt in attempts_by_id.values():
                deleted_log_paths.extend(self._collect_attempt_log_paths([attempt]))
                attempt.stdout_path = None
                attempt.stderr_path = None

        if prune_events:
            deleted_event_count += self._delete_old_terminal_events(session, cutoff_at=cutoff_at)

        session.flush()
        return RetentionCleanupResult(
            cutoff_at=cutoff_at,
            pruned_attempts=prune_attempts,
            pruned_events=prune_events,
            pruned_logs=prune_logs,
            deleted_attempt_count=deleted_attempt_count,
            deleted_event_count=deleted_event_count,
            deleted_log_paths=deleted_log_paths,
        )

    def _list_prunable_attempts(self, session: Session, *, cutoff_at: datetime) -> list[AttemptModel]:
        statement: Select[tuple[AttemptModel]] = (
            select(AttemptModel)
            .options(selectinload(AttemptModel.job))
            .join(JobModel, AttemptModel.job_id == JobModel.id)
            .where(JobModel.state.in_(TERMINAL_JOB_STATES))
            .where(AttemptModel.finished_at.is_not(None))
            .where(AttemptModel.finished_at <= cutoff_at)
        )
        return session.execute(statement).scalars().all()

    def _delete_attempt_events(self, session: Session, *, attempt_ids: list[int]) -> int:
        deleted_event_count = 0
        events = session.execute(select(EventModel).where(EventModel.attempt_id.in_(attempt_ids))).scalars().all()
        for event in events:
            session.delete(event)
            deleted_event_count += 1
        return deleted_event_count

    def _delete_old_terminal_events(self, session: Session, *, cutoff_at: datetime) -> int:
        deleted_event_count = 0
        events = session.execute(
            select(EventModel)
            .outerjoin(JobModel, EventModel.job_id == JobModel.id)
            .where(EventModel.created_at <= cutoff_at)
            .where((EventModel.job_id.is_(None)) | (JobModel.state.in_(TERMINAL_JOB_STATES)))
        ).scalars().all()
        for event in events:
            session.delete(event)
            deleted_event_count += 1
        return deleted_event_count

    def _collect_attempt_log_paths(self, attempts) -> list[str]:
        return [
            path
            for attempt in attempts
            for path in [attempt.stdout_path, attempt.stderr_path]
            if path is not None
        ]
