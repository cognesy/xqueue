from __future__ import annotations

from datetime import UTC, datetime

from libs.domain.models import AttemptState, AttemptView, JobDetail, JobState, JobSummary, WorkerState, WorkerView
from libs.domain.responses import DetailResponse, ErrorDetail, ErrorResponse, ListResponse, MutationResponse


def test_job_and_worker_enums_use_spec_vocabulary() -> None:
    assert JobState.RETRY_SCHEDULED.value == "retry_scheduled"
    assert WorkerState.DRAINING.value == "draining"
    assert AttemptState.TIMED_OUT.value == "timed_out"


def test_list_detail_and_mutation_responses_serialize_stably() -> None:
    created_at = datetime(2026, 3, 22, 20, 0, tzinfo=UTC)
    summary = JobSummary(
        id="job-1",
        queue="agent",
        command="echo hi",
        state=JobState.QUEUED,
        priority=100,
        created_at=created_at,
        available_at=created_at,
    )

    list_payload = ListResponse(items=[summary]).model_dump()
    detail_payload = DetailResponse(item=summary).model_dump()
    mutation_payload = MutationResponse(item=summary).model_dump()

    assert list_payload == {"items": [summary.model_dump()], "meta": None}
    assert detail_payload == {"item": summary.model_dump()}
    assert mutation_payload == {"ok": True, "item": summary.model_dump()}


def test_error_response_uses_structured_shape() -> None:
    response = ErrorResponse(
        error=ErrorDetail(
            code="not_found",
            message="job not found",
            details={"job_id": "job-1"},
        )
    )

    assert response.model_dump() == {
        "ok": False,
        "error": {
            "code": "not_found",
            "message": "job not found",
            "details": {"job_id": "job-1"},
        },
    }


def test_job_detail_and_worker_view_remain_presentation_neutral() -> None:
    created_at = datetime(2026, 3, 22, 20, 0, tzinfo=UTC)
    attempt = AttemptView(
        attempt_number=1,
        state=AttemptState.SUCCEEDED,
        started_at=created_at,
        finished_at=created_at,
        exit_code=0,
    )
    detail = JobDetail(
        id="job-1",
        queue="agent",
        command="echo hi",
        state=JobState.SUCCEEDED,
        priority=10,
        created_at=created_at,
        available_at=created_at,
        shell=True,
        max_attempts=3,
        attempts=[attempt],
    )
    worker = WorkerView(
        id="worker-1",
        state=WorkerState.ACTIVE,
        queues=["agent"],
        started_at=created_at,
    )

    assert detail.attempts[0].state is AttemptState.SUCCEEDED
    assert worker.queues == ["agent"]
    assert "ok" not in detail.model_dump()
