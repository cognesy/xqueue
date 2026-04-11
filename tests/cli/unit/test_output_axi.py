from __future__ import annotations

import json
from datetime import UTC, datetime

import click
import pytest
from toon import decode
from typer import Context

from apps.cli.output import Output, OutputFormat
from libs.domain.models import JobState, JobSummary
from libs.domain.responses import ErrorDetail, ErrorResponse, ListResponse


def _build_context(output: OutputFormat) -> Context:
    return Context(click.Command("test"), obj={"output": output, "fields": None, "full": False})


def _sample_response() -> ListResponse[JobSummary]:
    created_at = datetime(2026, 4, 10, 20, 0, tzinfo=UTC)
    return ListResponse(
        items=[
            JobSummary(
                id="job-1",
                queue="agent",
                command="echo hi",
                state=JobState.QUEUED,
                priority=100,
                created_at=created_at,
                available_at=created_at,
            )
        ]
    )


def test_output_render_json() -> None:
    out = Output(_build_context(OutputFormat.JSON), "jobs.list")

    rendered = out.render(_sample_response())
    payload = json.loads(rendered)

    assert out.contract.name == "jobs.list"
    assert payload["items"][0]["id"] == "job-1"
    assert payload["items"][0]["state"] == "queued"
    assert payload["meta"] is None


def test_output_render_jsonl() -> None:
    out = Output(_build_context(OutputFormat.JSONL), "jobs.list")

    rendered = out.render(_sample_response())
    lines = rendered.splitlines()

    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == "job-1"


def test_output_render_toon() -> None:
    out = Output(_build_context(OutputFormat.TOON), "jobs.list")

    rendered = out.render(_sample_response())
    payload = decode(rendered)

    assert payload["items"][0]["id"] == "job-1"
    assert payload["items"][0]["queue"] == "agent"


def test_output_render_text() -> None:
    out = Output(_build_context(OutputFormat.TEXT), "jobs.list")

    rendered = out.render(_sample_response())

    assert "job-1" in rendered
    assert "queued" in rendered


def test_output_error_renders_json_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    out = Output(_build_context(OutputFormat.JSON), "jobs.list")

    with pytest.raises(click.exceptions.Exit) as exc_info:
        out.error("bad input", code="validation_error", details={"field": "queue"}, exit_code=2)

    captured = capsys.readouterr()
    assert exc_info.value.exit_code == 2
    payload = json.loads(captured.out)
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["details"] == {"field": "queue"}


def test_output_error_renders_toon_to_stdout() -> None:
    out = Output(_build_context(OutputFormat.TOON), "error")
    payload = decode(
        out.render(
            ErrorResponse(
                error=ErrorDetail(
                    code="not_found",
                    message="missing job",
                    details={"job_id": "job-1"},
                )
            )
        )
    )
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["details"]["job_id"] == "job-1"
