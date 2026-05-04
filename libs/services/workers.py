"""Worker persistence and claim services."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import insert, or_, select, update
from sqlalchemy.orm import Session

from xqueue_libs.domain.errors import NotFoundError
from xqueue_libs.domain.models import JobDetail, JobState, RegisterWorkerInput, WorkerState, WorkerView
from xqueue_libs.infra.models import JobModel, WorkerModel
from xqueue_libs.services.datetimes import ensure_utc
from xqueue_libs.services.jobs import JobService
from xqueue_libs.services.queues import QueueService


class WorkerService:
    """Persist worker lifecycle state and claim runnable jobs."""

    def __init__(
        self,
        job_service: JobService | None = None,
        queue_service: QueueService | None = None,
    ) -> None:
        self._job_service = job_service or JobService()
        self._queue_service = queue_service or QueueService()

    def register_worker(self, session: Session, *, payload: RegisterWorkerInput, now: datetime) -> WorkerView:
        model = session.get(WorkerModel, payload.worker_id)
        if model is None:
            session.execute(
                insert(WorkerModel)
                .values(
                    id=payload.worker_id,
                    started_at=now,
                    state=payload.state.value,
                )
                .prefix_with("OR IGNORE")
            )
            model = session.get(WorkerModel, payload.worker_id)
            if model is None:
                raise NotFoundError("worker not found after registration", details={"worker_id": payload.worker_id})
        elif payload.state is not WorkerState.ACTIVE:
            model.state = payload.state.value
        model.queues = payload.queues
        model.heartbeat_at = now
        model.hostname = payload.hostname
        model.process_id = payload.process_id
        model.concurrency = payload.concurrency
        session.flush()
        return self.to_worker_view(model)

    def heartbeat_worker(
        self,
        session: Session,
        *,
        worker_id: str,
        now: datetime,
        state: WorkerState | None = None,
    ) -> WorkerView:
        model = session.get(WorkerModel, worker_id)
        if model is None:
            raise NotFoundError("worker not found", details={"worker_id": worker_id})
        model.heartbeat_at = now
        if state is not None:
            model.state = state.value
        session.flush()
        return self.to_worker_view(model)

    def claim_next_job(
        self,
        session: Session,
        *,
        worker_id: str,
        queues: list[str],
        now: datetime,
        lease_expires_at: datetime,
    ) -> JobDetail | None:
        worker = session.get(WorkerModel, worker_id)
        if worker is None or worker.state != WorkerState.ACTIVE.value:
            return None

        paused_queues = self._queue_service.paused_queue_names(session, queues=queues)
        eligible_queues = [queue for queue in queues if queue not in paused_queues]
        if not eligible_queues:
            return None

        candidate_states = (JobState.QUEUED.value, JobState.RETRY_SCHEDULED.value)

        while True:
            candidate_id = session.execute(
                select(JobModel.id)
                .where(JobModel.state.in_(candidate_states))
                .where(JobModel.queue.in_(eligible_queues))
                .where(JobModel.available_at <= now)
                .where(or_(JobModel.lease_expires_at.is_(None), JobModel.lease_expires_at <= now))
                .order_by(JobModel.priority.asc(), JobModel.created_at.asc(), JobModel.id.asc())
                .limit(1)
            ).scalar_one_or_none()

            if candidate_id is None:
                return None

            result = session.execute(
                update(JobModel)
                .where(JobModel.id == candidate_id)
                .where(JobModel.state.in_(candidate_states))
                .where(or_(JobModel.worker_id.is_(None), JobModel.lease_expires_at <= now))
                .values(
                    state=JobState.RUNNING.value,
                    worker_id=worker_id,
                    lease_expires_at=lease_expires_at,
                )
            )
            if result.rowcount == 1:
                session.flush()
                model = session.get(JobModel, candidate_id)
                if model is None:
                    return None
                return self._job_service.to_job_detail(model)

    def renew_job_lease(
        self,
        session: Session,
        *,
        job_id: str,
        worker_id: str,
        lease_expires_at: datetime,
    ) -> bool:
        result = session.execute(
            update(JobModel)
            .where(JobModel.id == job_id)
            .where(JobModel.state == JobState.RUNNING.value)
            .where(JobModel.worker_id == worker_id)
            .values(lease_expires_at=lease_expires_at)
        )
        session.flush()
        return result.rowcount == 1

    def set_worker_state(
        self,
        session: Session,
        *,
        worker_id: str,
        state: WorkerState,
        now: datetime,
        touch_heartbeat: bool = True,
    ) -> WorkerView:
        model = session.get(WorkerModel, worker_id)
        if model is None:
            raise NotFoundError("worker not found", details={"worker_id": worker_id})
        model.state = state.value
        if touch_heartbeat:
            model.heartbeat_at = now
        session.flush()
        return self.to_worker_view(model)

    def list_workers(self, session: Session) -> list[WorkerView]:
        models = session.execute(select(WorkerModel).order_by(WorkerModel.started_at.asc(), WorkerModel.id.asc())).scalars().all()
        return [self.to_worker_view(model) for model in models]

    def to_worker_view(self, model: WorkerModel) -> WorkerView:
        return WorkerView(
            id=model.id,
            state=WorkerState(model.state),
            queues=model.queues or [],
            heartbeat_at=ensure_utc(model.heartbeat_at),
            started_at=ensure_utc(model.started_at),
            hostname=model.hostname,
            process_id=model.process_id,
            concurrency=model.concurrency,
        )
