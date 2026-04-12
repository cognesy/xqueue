"""Job pruning service for cleaning up terminal job history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from libs.domain.models import JobPruneResult, JobPruneSummary, JobState
from libs.infra.models import AttemptModel, EventModel, JobModel


TERMINAL_JOB_STATES = (
    JobState.SUCCEEDED.value,
    JobState.FAILED.value,
    JobState.CANCELED.value,
    JobState.TIMED_OUT.value,
    JobState.DEAD.value,
)

NON_RUNNING_STATES = tuple(s.value for s in JobState if s is not JobState.RUNNING)


class JobPruningService:
    """Prune terminal jobs and their associated history."""

    def prune(
        self,
        session: Session,
        *,
        state_filter: str | None,
        cutoff_at: datetime | None,
        prune_logs: bool,
        dry_run: bool,
    ) -> JobPruneResult:
        target_states = self._resolve_target_states(state_filter)
        statement = self._build_query(target_states=target_states, cutoff_at=cutoff_at)
        models = session.execute(statement).scalars().all()

        matched_jobs = [
            JobPruneSummary(
                id=m.id,
                queue=m.queue,
                state=JobState(m.state),
                attempt_count=len(m.attempts),
                created_at=m.created_at,
            )
            for m in models
        ]

        if dry_run:
            log_paths = self._collect_log_paths(models) if prune_logs else []
            return JobPruneResult(
                dry_run=True,
                state_filter=state_filter,
                older_than=None,
                cutoff_at=cutoff_at,
                matched_job_count=len(models),
                deleted_job_count=0,
                deleted_attempt_count=0,
                deleted_event_count=0,
                deleted_log_count=len(log_paths),
                deleted_log_paths=log_paths,
                matched_jobs=matched_jobs,
            )

        deleted_attempt_count = 0
        deleted_event_count = 0
        log_paths: list[str] = []

        for model in models:
            if prune_logs:
                log_paths.extend(self._collect_log_paths([model]))
            for event in list(model.events):
                session.delete(event)
                deleted_event_count += 1
            for attempt in list(model.attempts):
                session.delete(attempt)
                deleted_attempt_count += 1
            session.delete(model)

        session.flush()

        return JobPruneResult(
            dry_run=False,
            state_filter=state_filter,
            older_than=None,
            cutoff_at=cutoff_at,
            matched_job_count=len(models),
            deleted_job_count=len(models),
            deleted_attempt_count=deleted_attempt_count,
            deleted_event_count=deleted_event_count,
            deleted_log_count=0,
            deleted_log_paths=log_paths,
            matched_jobs=matched_jobs,
        )

    def _resolve_target_states(self, state_filter: str | None) -> tuple[str, ...]:
        if state_filter is None:
            return TERMINAL_JOB_STATES
        if state_filter == "terminal":
            return TERMINAL_JOB_STATES
        state = JobState(state_filter)
        if state is JobState.RUNNING:
            raise ValueError("cannot prune running jobs")
        return (state.value,)

    def _build_query(
        self,
        *,
        target_states: tuple[str, ...],
        cutoff_at: datetime | None,
    ) -> Select[tuple[JobModel]]:
        statement: Select[tuple[JobModel]] = (
            select(JobModel)
            .options(selectinload(JobModel.attempts), selectinload(JobModel.events))
            .where(JobModel.state.in_(target_states))
        )
        if cutoff_at is not None:
            statement = statement.where(JobModel.created_at <= cutoff_at)
        return statement.order_by(JobModel.created_at.asc())

    def _collect_log_paths(self, models: list[JobModel]) -> list[str]:
        return [
            path
            for model in models
            for attempt in model.attempts
            for path in [attempt.stdout_path, attempt.stderr_path]
            if path is not None
        ]
