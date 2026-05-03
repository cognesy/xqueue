"""Attempt lifecycle services for worker execution."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from libs.domain.errors import NotFoundError
from libs.domain.models import AttemptLogPaths, AttemptState, JobDetail, JobState, ProcessExecutionResult, StartedAttempt
from libs.infra.models import AttemptModel, EventModel, JobModel
from libs.services.jobs import JobService


class AttemptService:
    """Create and finalize execution attempts without leaking ORM to app shells."""

    def __init__(self, job_service: JobService | None = None) -> None:
        self._job_service = job_service or JobService()

    def start_attempt(
        self,
        session: Session,
        *,
        job_id: str,
        worker_id: str,
        log_paths: AttemptLogPaths,
        now: datetime,
    ) -> StartedAttempt:
        job = session.get(JobModel, job_id)
        if job is None:
            raise NotFoundError("job not found", details={"job_id": job_id})

        attempt_number = job.attempt_count + 1
        attempt = AttemptModel(
            job_id=job.id,
            attempt_number=attempt_number,
            worker_id=worker_id,
            state=AttemptState.RUNNING.value,
            started_at=now,
            stdout_path=log_paths.stdout_path,
            stderr_path=log_paths.stderr_path,
        )
        session.add(attempt)
        job.attempt_count = attempt_number
        job.last_exit_code = None
        job.last_error = None
        session.flush()
        session.add(EventModel(
            event_type="job.started",
            created_at=now,
            job_id=job.id,
            attempt_id=attempt.id,
            payload={"attempt_number": attempt_number, "worker_id": worker_id},
        ))
        session.flush()
        return StartedAttempt(
            id=attempt.id,
            attempt_number=attempt.attempt_number,
            started_at=attempt.started_at,
            stdout_path=attempt.stdout_path or "",
            stderr_path=attempt.stderr_path or "",
            event_log_path=log_paths.event_log_path,
        )

    def finalize_attempt(
        self,
        session: Session,
        *,
        attempt_id: int,
        result: ProcessExecutionResult,
        retry_delay_seconds: int,
    ) -> JobDetail:
        attempt = session.get(AttemptModel, attempt_id)
        if attempt is None:
            raise NotFoundError("attempt not found", details={"attempt_id": attempt_id})

        job = attempt.job
        if job is None:
            raise NotFoundError("job not found", details={"job_id": attempt.job_id})

        attempt.finished_at = result.finished_at
        attempt.exit_code = result.exit_code
        attempt.stdout_path = result.stdout_path
        attempt.stderr_path = result.stderr_path

        job.last_exit_code = result.exit_code
        job.worker_id = None
        job.lease_expires_at = None

        if result.canceled:
            attempt.state = AttemptState.CANCELED.value
            attempt.error = "canceled"
            attempt.cancellation_reason = result.cancellation_reason or "operator_requested"
            job.state = JobState.CANCELED.value
            job.last_error = "canceled"
            session.flush()
            session.add(EventModel(
                event_type="job.canceled",
                created_at=result.finished_at,
                job_id=job.id,
                attempt_id=attempt.id,
                payload={"cancellation_reason": attempt.cancellation_reason},
            ))
        elif result.timed_out:
            attempt.state = AttemptState.TIMED_OUT.value
            attempt.error = "timed out"
            job.last_error = "timed out"
            self._apply_failure_outcome(job, finished_at=result.finished_at, retry_delay_seconds=retry_delay_seconds)
            session.flush()
            session.add(EventModel(
                event_type="job.timed_out",
                created_at=result.finished_at,
                job_id=job.id,
                attempt_id=attempt.id,
                payload={"error": "timed out"},
            ))
            if job.state == JobState.RETRY_SCHEDULED.value:
                session.add(EventModel(
                    event_type="job.retry_scheduled",
                    created_at=result.finished_at,
                    job_id=job.id,
                    attempt_id=attempt.id,
                    payload={"attempt_count": job.attempt_count, "available_at": job.available_at.isoformat()},
                ))
        elif result.exit_code == 0:
            attempt.state = AttemptState.SUCCEEDED.value
            attempt.error = None
            attempt.cancellation_reason = None
            job.state = JobState.SUCCEEDED.value
            job.last_error = None
            session.flush()
            session.add(EventModel(
                event_type="job.succeeded",
                created_at=result.finished_at,
                job_id=job.id,
                attempt_id=attempt.id,
                payload={"exit_code": 0},
            ))
        else:
            attempt.state = AttemptState.FAILED.value
            attempt.error = self._failure_message(result.exit_code)
            attempt.cancellation_reason = None
            job.last_error = attempt.error
            self._apply_failure_outcome(job, finished_at=result.finished_at, retry_delay_seconds=retry_delay_seconds)
            session.flush()
            session.add(EventModel(
                event_type="job.failed",
                created_at=result.finished_at,
                job_id=job.id,
                attempt_id=attempt.id,
                payload={"exit_code": result.exit_code, "error": attempt.error},
            ))
            if job.state == JobState.RETRY_SCHEDULED.value:
                session.add(EventModel(
                    event_type="job.retry_scheduled",
                    created_at=result.finished_at,
                    job_id=job.id,
                    attempt_id=attempt.id,
                    payload={"attempt_count": job.attempt_count, "available_at": job.available_at.isoformat()},
                ))

        session.flush()
        session.refresh(job, attribute_names=["attempts"])
        return self._job_service.to_job_detail(job)

    def _apply_failure_outcome(self, job: JobModel, *, finished_at: datetime, retry_delay_seconds: int) -> None:
        if job.attempt_count < job.max_attempts:
            job.state = JobState.RETRY_SCHEDULED.value
            job.available_at = finished_at + timedelta(seconds=retry_delay_seconds)
        else:
            job.state = JobState.FAILED.value

    def _failure_message(self, exit_code: int | None) -> str:
        if exit_code is None:
            return "command failed before producing an exit code"
        return f"command exited with code {exit_code}"
