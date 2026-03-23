"""Job persistence services."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, asc, desc, select
from sqlalchemy.orm import Session, selectinload

from libs.domain.errors import ConflictError, NotFoundError
from libs.domain.models import (
    AttemptLogStream,
    AttemptState,
    AttemptView,
    DeleteJobResult,
    EnqueueJobInput,
    EventView,
    JobDetail,
    JobListFilters,
    JobListSort,
    JobLogTailView,
    JobState,
    JobSummary,
)
from libs.infra.models import AttemptModel, EventModel, JobModel
from libs.services.datetimes import ensure_utc


class JobService:
    """Persist and query job records."""

    def enqueue(self, session: Session, *, job_id: str, payload: EnqueueJobInput, now: datetime) -> JobDetail:
        available_at = payload.available_at or now
        model = JobModel(
            id=job_id,
            queue=payload.queue,
            command=payload.command,
            shell=payload.shell,
            cwd=payload.cwd,
            env=payload.env,
            priority=payload.priority,
            timeout_seconds=payload.timeout_seconds,
            max_attempts=payload.max_attempts,
            created_at=now,
            available_at=available_at,
            state=JobState.QUEUED.value,
            created_by=payload.created_by,
        )
        session.add(model)
        session.flush()
        session.add(EventModel(
            event_type="job.enqueued",
            created_at=now,
            job_id=model.id,
            payload={"queue": payload.queue, "priority": payload.priority, "max_attempts": payload.max_attempts},
        ))
        session.flush()
        return self.to_job_detail(model)

    def list_jobs(self, session: Session, *, filters: JobListFilters) -> list[JobSummary]:
        statement: Select[tuple[JobModel]] = select(JobModel)
        if filters.queue is not None:
            statement = statement.where(JobModel.queue == filters.queue)
        if filters.state is not None:
            statement = statement.where(JobModel.state == filters.state.value)
        if filters.worker_id is not None:
            statement = statement.where(JobModel.worker_id == filters.worker_id)
        if filters.created_after is not None:
            statement = statement.where(JobModel.created_at >= filters.created_after)
        if filters.created_before is not None:
            statement = statement.where(JobModel.created_at <= filters.created_before)
        if filters.available_after is not None:
            statement = statement.where(JobModel.available_at >= filters.available_after)
        if filters.available_before is not None:
            statement = statement.where(JobModel.available_at <= filters.available_before)

        statement = statement.order_by(*self._job_list_order_by(filters.sort)).limit(filters.limit)

        models = session.execute(statement).scalars().all()
        return [self.to_job_summary(model) for model in models]

    def get_job(self, session: Session, *, job_id: str) -> JobDetail:
        statement = (
            select(JobModel)
            .options(selectinload(JobModel.attempts), selectinload(JobModel.events))
            .where(JobModel.id == job_id)
        )
        model = session.execute(statement).scalar_one_or_none()
        if model is None:
            raise NotFoundError("job not found", details={"job_id": job_id})
        return self.to_job_detail(model)

    def cancel_job(self, session: Session, *, job_id: str, now: datetime) -> JobDetail:
        model = self._get_job_model(session, job_id=job_id)
        state = JobState(model.state)

        if state in {JobState.QUEUED, JobState.RETRY_SCHEDULED}:
            model.state = JobState.CANCELED.value
            model.cancel_requested_at = now
            model.worker_id = None
            model.lease_expires_at = None
            model.last_error = "canceled"
            session.add(EventModel(
                event_type="job.canceled",
                created_at=now,
                job_id=model.id,
                payload={"reason": "operator_requested"},
            ))
        elif state is JobState.RUNNING:
            model.cancel_requested_at = now
            session.add(EventModel(
                event_type="job.cancel_requested",
                created_at=now,
                job_id=model.id,
                payload={},
            ))
        else:
            raise ConflictError(
                "job cannot be canceled in its current state",
                details={"job_id": job_id, "state": model.state},
            )

        session.flush()
        session.refresh(model, attribute_names=["attempts"])
        return self.to_job_detail(model)

    def retry_job(self, session: Session, *, job_id: str, now: datetime) -> JobDetail:
        model = self._get_job_model(session, job_id=job_id)
        state = JobState(model.state)
        _retryable_states = {JobState.FAILED, JobState.CANCELED, JobState.TIMED_OUT, JobState.DEAD}
        if state not in _retryable_states:
            raise ConflictError(
                "job cannot be retried in its current state",
                details={"job_id": job_id, "state": model.state},
            )

        model.state = JobState.QUEUED.value
        model.available_at = now
        model.worker_id = None
        model.lease_expires_at = None
        model.cancel_requested_at = None
        model.last_exit_code = None
        model.last_error = None
        session.add(EventModel(
            event_type="job.requeued",
            created_at=now,
            job_id=model.id,
            payload={"attempt_count": model.attempt_count},
        ))
        session.flush()
        session.refresh(model, attribute_names=["attempts"])
        return self.to_job_detail(model)

    def delete_job(self, session: Session, *, job_id: str) -> DeleteJobResult:
        statement = (
            select(JobModel)
            .options(selectinload(JobModel.attempts), selectinload(JobModel.events))
            .where(JobModel.id == job_id)
        )
        model = session.execute(statement).scalar_one_or_none()
        if model is None:
            raise NotFoundError("job not found", details={"job_id": job_id})

        state = JobState(model.state)
        if state is JobState.RUNNING:
            raise ConflictError(
                "running jobs cannot be deleted",
                details={"job_id": job_id, "state": model.state},
            )

        log_paths = [
            path
            for attempt in model.attempts
            for path in [attempt.stdout_path, attempt.stderr_path]
            if path is not None
        ]
        deleted_attempt_count = len(model.attempts)
        deleted_event_count = len(model.events)

        for event in list(model.events):
            session.delete(event)
        for attempt in list(model.attempts):
            session.delete(attempt)
        session.delete(model)
        session.flush()

        return DeleteJobResult(
            job_id=job_id,
            deleted_state=state,
            deleted_attempt_count=deleted_attempt_count,
            deleted_event_count=deleted_event_count,
            deleted_log_paths=log_paths,
        )

    def get_job_log_tail(
        self,
        session: Session,
        *,
        job_id: str,
        stream: AttemptLogStream,
        attempt_number: int | None = None,
    ) -> JobLogTailView:
        model = self._get_job_model(session, job_id=job_id)
        attempts = sorted(model.attempts, key=lambda item: item.attempt_number)
        if not attempts:
            raise NotFoundError("job has no attempts to tail", details={"job_id": job_id})

        attempt = attempts[-1] if attempt_number is None else next(
            (item for item in attempts if item.attempt_number == attempt_number),
            None,
        )
        if attempt is None:
            raise NotFoundError(
                "attempt not found for job",
                details={"job_id": job_id, "attempt_number": attempt_number},
            )

        path = attempt.stdout_path if stream is AttemptLogStream.STDOUT else attempt.stderr_path
        if path is None:
            raise NotFoundError(
                "requested log stream is unavailable for attempt",
                details={"job_id": job_id, "attempt_number": attempt.attempt_number, "stream": stream.value},
            )

        return JobLogTailView(
            job_id=job_id,
            attempt_number=attempt.attempt_number,
            stream=stream,
            path=path,
        )

    def is_cancel_requested(self, session: Session, *, job_id: str) -> bool:
        model = self._get_job_model(session, job_id=job_id)
        return model.cancel_requested_at is not None

    def to_job_summary(self, model: JobModel) -> JobSummary:
        return JobSummary(
            id=model.id,
            queue=model.queue,
            command=model.command,
            state=JobState(model.state),
            priority=model.priority,
            created_at=ensure_utc(model.created_at),
            available_at=ensure_utc(model.available_at),
            worker_id=model.worker_id,
            attempt_count=model.attempt_count,
            last_exit_code=model.last_exit_code,
            last_error=model.last_error,
        )

    def _job_list_order_by(self, sort: JobListSort):
        if sort is JobListSort.CREATED_ASC:
            return (asc(JobModel.created_at), asc(JobModel.id))
        if sort is JobListSort.AVAILABLE_ASC:
            return (asc(JobModel.available_at), asc(JobModel.created_at), asc(JobModel.id))
        if sort is JobListSort.AVAILABLE_DESC:
            return (desc(JobModel.available_at), desc(JobModel.created_at), desc(JobModel.id))
        if sort is JobListSort.PRIORITY_ASC:
            return (asc(JobModel.priority), asc(JobModel.created_at), asc(JobModel.id))
        if sort is JobListSort.PRIORITY_DESC:
            return (desc(JobModel.priority), desc(JobModel.created_at), desc(JobModel.id))
        return (desc(JobModel.created_at), desc(JobModel.id))

    def _get_job_model(self, session: Session, *, job_id: str) -> JobModel:
        model = session.get(JobModel, job_id)
        if model is None:
            raise NotFoundError("job not found", details={"job_id": job_id})
        return model

    def to_job_detail(self, model: JobModel) -> JobDetail:
        return JobDetail(
            **self.to_job_summary(model).model_dump(),
            shell=model.shell,
            cwd=model.cwd,
            env=model.env,
            timeout_seconds=model.timeout_seconds,
            max_attempts=model.max_attempts,
            lease_expires_at=ensure_utc(model.lease_expires_at),
            cancel_requested_at=ensure_utc(model.cancel_requested_at),
            created_by=model.created_by,
            attempts=[
                self.to_attempt_view(attempt)
                for attempt in sorted(model.attempts, key=lambda item: item.attempt_number)
            ],
            events=[
                self.to_event_view(event)
                for event in sorted(model.events, key=lambda item: (item.created_at, item.id or 0))
            ],
        )

    def to_attempt_view(self, model: AttemptModel) -> AttemptView:
        return AttemptView(
            id=model.id,
            attempt_number=model.attempt_number,
            worker_id=model.worker_id,
            state=AttemptState(model.state),
            started_at=ensure_utc(model.started_at),
            finished_at=ensure_utc(model.finished_at),
            exit_code=model.exit_code,
            error=model.error,
            cancellation_reason=model.cancellation_reason,
            stdout_path=model.stdout_path,
            stderr_path=model.stderr_path,
        )

    def to_event_view(self, model: EventModel) -> EventView:
        return EventView(
            id=model.id,
            event_type=model.event_type,
            created_at=ensure_utc(model.created_at),
            payload=model.payload,
        )
