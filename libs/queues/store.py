"""SQLite queue adapter."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session
from xqueue.adapters.sqlite.models import AttemptModel, EventModel, JobModel, QueueModel
from xqueue.core.datetimes import ensure_utc
from xqueue.jobs.models import JobState
from xqueue.queues.models import PurgeJobsResult, QueueState, QueueStatsView, QueueView


class QueueService:
    """Persist queue control state and compute queue-level views."""

    def list_queues(self, session: Session) -> list[QueueView]:
        queue_rows = session.execute(select(QueueModel).order_by(QueueModel.name.asc())).scalars().all()
        known_names = {row.name for row in queue_rows}
        job_names = set(session.execute(select(JobModel.queue).distinct()).scalars().all())
        names = sorted(known_names | job_names)

        row_map = {row.name: row for row in queue_rows}
        return [self._to_queue_view(row_map.get(name), name=name) for name in names]

    def list_queue_stats(self, session: Session) -> list[QueueStatsView]:
        queue_views = self.list_queues(session)
        counts = {
            row.queue: {
                "total_jobs": row.total_jobs,
                "queued_jobs": row.queued_jobs,
                "running_jobs": row.running_jobs,
                "retry_scheduled_jobs": row.retry_scheduled_jobs,
                "succeeded_jobs": row.succeeded_jobs,
                "failed_jobs": row.failed_jobs,
                "canceled_jobs": row.canceled_jobs,
                "timed_out_jobs": row.timed_out_jobs,
                "dead_jobs": row.dead_jobs,
            }
            for row in session.execute(
                select(
                    JobModel.queue.label("queue"),
                    func.count().label("total_jobs"),
                    func.sum(case((JobModel.state == JobState.QUEUED.value, 1), else_=0)).label("queued_jobs"),
                    func.sum(case((JobModel.state == JobState.RUNNING.value, 1), else_=0)).label("running_jobs"),
                    func.sum(case((JobModel.state == JobState.RETRY_SCHEDULED.value, 1), else_=0)).label(
                        "retry_scheduled_jobs"
                    ),
                    func.sum(case((JobModel.state == JobState.SUCCEEDED.value, 1), else_=0)).label("succeeded_jobs"),
                    func.sum(case((JobModel.state == JobState.FAILED.value, 1), else_=0)).label("failed_jobs"),
                    func.sum(case((JobModel.state == JobState.CANCELED.value, 1), else_=0)).label("canceled_jobs"),
                    func.sum(case((JobModel.state == JobState.TIMED_OUT.value, 1), else_=0)).label("timed_out_jobs"),
                    func.sum(case((JobModel.state == JobState.DEAD.value, 1), else_=0)).label("dead_jobs"),
                ).group_by(JobModel.queue)
            )
        }

        items: list[QueueStatsView] = []
        for queue_view in queue_views:
            item_counts = counts.get(queue_view.name, {})
            items.append(
                QueueStatsView(
                    name=queue_view.name,
                    state=queue_view.state,
                    paused_at=queue_view.paused_at,
                    total_jobs=item_counts.get("total_jobs", 0) or 0,
                    queued_jobs=item_counts.get("queued_jobs", 0) or 0,
                    running_jobs=item_counts.get("running_jobs", 0) or 0,
                    retry_scheduled_jobs=item_counts.get("retry_scheduled_jobs", 0) or 0,
                    succeeded_jobs=item_counts.get("succeeded_jobs", 0) or 0,
                    failed_jobs=item_counts.get("failed_jobs", 0) or 0,
                    canceled_jobs=item_counts.get("canceled_jobs", 0) or 0,
                    timed_out_jobs=item_counts.get("timed_out_jobs", 0) or 0,
                    dead_jobs=item_counts.get("dead_jobs", 0) or 0,
                )
            )
        return items

    def pause_queue(self, session: Session, *, queue: str, now: datetime) -> QueueView:
        model = session.get(QueueModel, queue)
        if model is None:
            model = QueueModel(name=queue, state=QueueState.ACTIVE.value, updated_at=now)
            session.add(model)

        model.state = QueueState.PAUSED.value
        model.updated_at = now
        model.paused_at = now
        session.flush()
        return self._to_queue_view(model)

    def resume_queue(self, session: Session, *, queue: str, now: datetime) -> QueueView:
        model = session.get(QueueModel, queue)
        if model is None:
            model = QueueModel(name=queue, state=QueueState.ACTIVE.value, updated_at=now)
            session.add(model)

        model.state = QueueState.ACTIVE.value
        model.updated_at = now
        model.paused_at = None
        session.flush()
        return self._to_queue_view(model)

    def purge_jobs(self, session: Session, *, queue: str) -> PurgeJobsResult:
        purgeable_states = [JobState.QUEUED.value, JobState.RETRY_SCHEDULED.value]
        job_ids = list(
            session.execute(
                select(JobModel.id).where(JobModel.queue == queue).where(JobModel.state.in_(purgeable_states))
            )
            .scalars()
            .all()
        )
        if not job_ids:
            return PurgeJobsResult(queue=queue, deleted_count=0)

        session.execute(delete(EventModel).where(EventModel.job_id.in_(job_ids)))
        session.execute(delete(AttemptModel).where(AttemptModel.job_id.in_(job_ids)))
        session.execute(delete(JobModel).where(JobModel.id.in_(job_ids)))
        session.flush()
        return PurgeJobsResult(queue=queue, deleted_count=len(job_ids))

    def paused_queue_names(self, session: Session, *, queues: list[str]) -> set[str]:
        if not queues:
            return set()
        return set(
            session.execute(
                select(QueueModel.name)
                .where(QueueModel.name.in_(queues))
                .where(QueueModel.state == QueueState.PAUSED.value)
            )
            .scalars()
            .all()
        )

    def _to_queue_view(self, model: QueueModel | None, *, name: str | None = None) -> QueueView:
        if model is None:
            return QueueView(name=name or "", state=QueueState.ACTIVE, paused_at=None)
        return QueueView(
            name=model.name,
            state=QueueState(model.state),
            paused_at=ensure_utc(model.paused_at),
        )
