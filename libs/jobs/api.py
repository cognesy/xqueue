"""Public SDK facet for job operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from xqueue.core.errors import ValidationError
from xqueue.jobs.models import (
    AttemptLogStream,
    DeleteJobResult,
    EnqueueJobInput,
    JobDetail,
    JobListFilters,
    JobLogTailView,
    JobPaneView,
    JobPruneResult,
    JobSummary,
)

if TYPE_CHECKING:
    from xqueue.runtime.composition import Runtime


class Jobs:
    """Typed job operations sharing one owned runtime."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def enqueue(self, payload: EnqueueJobInput | None = None, /, **fields: Any) -> JobDetail:
        """Enqueue one job from a validated input model or its field keywords.

        ``xq.jobs.enqueue(queue="agent", command="echo hi")`` and
        ``xq.jobs.enqueue(EnqueueJobInput(queue="agent", command="echo hi"))``
        are equivalent; the keyword form builds the same validated model, so
        ``EnqueueJobInput`` stays the single definition of the accepted fields.
        """
        self._runtime.ensure_open()
        if payload is None:
            payload = EnqueueJobInput(**fields)
        elif fields:
            raise ValidationError(
                "pass either an EnqueueJobInput or job field keywords, not both",
                details={"fields": sorted(fields)},
            )
        return self._runtime.job_actions.enqueue(payload)

    def list(self, filters: JobListFilters | None = None) -> list[JobSummary]:
        self._runtime.ensure_open()
        return self._runtime.job_actions.list(filters or JobListFilters())

    def show(self, job_id: str) -> JobDetail:
        self._runtime.ensure_open()
        return self._runtime.job_actions.show(job_id)

    def pane(self, job_id: str) -> JobPaneView:
        self._runtime.ensure_open()
        return self._runtime.job_actions.pane(job_id)

    def cancel(self, job_id: str) -> JobDetail:
        self._runtime.ensure_open()
        return self._runtime.job_actions.cancel(job_id)

    def retry(self, job_id: str) -> JobDetail:
        self._runtime.ensure_open()
        return self._runtime.job_actions.retry(job_id)

    def delete(self, job_id: str) -> DeleteJobResult:
        self._runtime.ensure_open()
        return self._runtime.job_actions.delete(job_id)

    def tail(
        self,
        job_id: str,
        *,
        stream: AttemptLogStream,
        lines: int,
        attempt_number: int | None = None,
    ) -> JobLogTailView:
        self._runtime.ensure_open()
        return self._runtime.job_actions.tail(
            job_id,
            stream=stream,
            lines=lines,
            attempt_number=attempt_number,
        )

    def prune(
        self,
        *,
        state: str | None,
        older_than: str | None,
        prune_logs: bool,
        dry_run: bool,
    ) -> JobPruneResult:
        self._runtime.ensure_open()
        return self._runtime.job_actions.prune(
            state=state,
            older_than=older_than,
            prune_logs=prune_logs,
            dry_run=dry_run,
        )
