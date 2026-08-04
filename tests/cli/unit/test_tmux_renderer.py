from __future__ import annotations

from xqueue_cli.renderers.tmux import render_tmux


def test_render_tmux_detail_response() -> None:
    payload = {
        "item": {
            "status": "ok",
            "database_status": "ok",
            "paused_queues": [],
            "stale_leases": [],
            "stale_workers": [],
        }
    }
    result = render_tmux(payload)
    assert "status=ok" in result
    assert "database_status=ok" in result
    assert "paused_queues=0" in result


def test_render_tmux_mutation_response() -> None:
    payload = {
        "ok": True,
        "item": {
            "job_id": "abc123",
            "deleted_state": "failed",
            "deleted_attempt_count": 2,
        },
    }
    result = render_tmux(payload)
    assert "job_id=abc123" in result
    assert "deleted_state=failed" in result
    assert "deleted_attempt_count=2" in result
    assert "ok=" not in result


def test_render_tmux_list_response_with_items() -> None:
    payload = {
        "items": [
            {"id": "job-1", "queue": "agent", "state": "queued", "available_at": "2026-01-01T00:00:00Z"},
            {"id": "job-2", "queue": "agent", "state": "failed", "available_at": "2026-01-01T00:01:00Z"},
        ],
        "meta": None,
    }
    result = render_tmux(payload)
    assert result.startswith("2 items")
    assert "job-1" in result
    assert "job-2" in result
    assert "queued" in result
    assert "failed" in result


def test_render_tmux_empty_list() -> None:
    payload = {"items": [], "meta": None}
    result = render_tmux(payload)
    assert result.startswith("0 items")


def test_render_tmux_error_response() -> None:
    payload = {
        "ok": False,
        "error": {"code": "not_found", "message": "job not found", "details": {}},
    }
    result = render_tmux(payload)
    assert result == "ERR not_found: job not found"


def test_render_tmux_formats_none_as_dash() -> None:
    payload = {"item": {"worker_id": None, "state": "queued"}}
    result = render_tmux(payload)
    assert "worker_id=-" in result


def test_render_tmux_formats_bool_as_yes_no() -> None:
    payload = {"ok": True, "item": {"dry_run": True, "count": 5}}
    result = render_tmux(payload)
    assert "dry_run=yes" in result
    assert "count=5" in result
