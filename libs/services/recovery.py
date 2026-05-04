"""Recovery services for stale worker leases."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from xqueue_libs.domain.models import JobState, RecoverStaleLeasesResult, RecoveredLeaseView, StaleLeaseView
from xqueue_libs.infra.models import AttemptModel, EventModel, JobModel
from xqueue_libs.services.datetimes import ensure_utc


RECOVERY_ERROR = "worker lease expired and job was recovered"


class RecoveryService:
    """Detect and recover stale running-job leases."""

    def list_stale_leases(self, session: Session, *, now: datetime) -> list[StaleLeaseView]:
        models = session.execute(
            select(JobModel)
            .where(JobModel.state == JobState.RUNNING.value)
            .where(JobModel.lease_expires_at.is_not(None))
            .where(JobModel.lease_expires_at < now)
            .order_by(JobModel.lease_expires_at.asc(), JobModel.id.asc())
        ).scalars().all()
        return [
            StaleLeaseView(
                job_id=model.id,
                queue=model.queue,
                worker_id=model.worker_id,
                lease_expires_at=ensure_utc(model.lease_expires_at),
                attempt_count=model.attempt_count,
            )
            for model in models
            if model.lease_expires_at is not None
        ]

    def recover_stale_leases(
        self,
        session: Session,
        *,
        now: datetime,
        retry_delay_seconds: int,
    ) -> RecoverStaleLeasesResult:
        jobs = session.execute(
            select(JobModel)
            .options(selectinload(JobModel.attempts))
            .where(JobModel.state == JobState.RUNNING.value)
            .where(JobModel.lease_expires_at.is_not(None))
            .where(JobModel.lease_expires_at < now)
            .order_by(JobModel.lease_expires_at.asc(), JobModel.id.asc())
        ).scalars().all()

        items: list[RecoveredLeaseView] = []
        for job in jobs:
            previous_worker_id = job.worker_id
            attempt = self._find_running_attempt(job)
            if attempt is not None:
                attempt.state = "failed"
                attempt.finished_at = now
                attempt.exit_code = None
                attempt.error = RECOVERY_ERROR
                attempt.cancellation_reason = None

            job.worker_id = None
            job.lease_expires_at = None
            job.last_exit_code = None
            job.last_error = RECOVERY_ERROR
            job.cancel_requested_at = None

            if job.attempt_count < job.max_attempts:
                job.state = JobState.RETRY_SCHEDULED.value
                job.available_at = now + timedelta(seconds=retry_delay_seconds)
                new_state = JobState.RETRY_SCHEDULED
            else:
                job.state = JobState.FAILED.value
                new_state = JobState.FAILED

            session.add(
                EventModel(
                    event_type="job.recovered_stale_lease",
                    created_at=now,
                    payload={
                        "recovery_error": RECOVERY_ERROR,
                        "previous_worker_id": previous_worker_id,
                        "attempt_id": None if attempt is None else attempt.id,
                        "new_state": new_state.value,
                    },
                    job_id=job.id,
                    attempt_id=None if attempt is None else attempt.id,
                    worker_id=previous_worker_id,
                )
            )

            items.append(
                RecoveredLeaseView(
                    job_id=job.id,
                    queue=job.queue,
                    previous_worker_id=previous_worker_id,
                    attempt_id=None if attempt is None else attempt.id,
                    recovered_at=ensure_utc(now),
                    new_state=new_state,
                    available_at=ensure_utc(job.available_at) if new_state is JobState.RETRY_SCHEDULED else None,
                )
            )

        session.flush()
        return RecoverStaleLeasesResult(recovered_count=len(items), items=items)

    def _find_running_attempt(self, job: JobModel) -> AttemptModel | None:
        running_attempts = [attempt for attempt in job.attempts if attempt.state == "running"]
        if not running_attempts:
            return None
        return max(running_attempts, key=lambda attempt: attempt.attempt_number)
