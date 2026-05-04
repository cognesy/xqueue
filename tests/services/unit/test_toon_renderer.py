from __future__ import annotations

from toon import decode

from xqueue_libs.services.toon_renderer import normalize_for_toon, render_toon


def test_normalize_for_toon_converts_container_types() -> None:
    payload = {
        1: ("alpha", "beta"),
        "nested": [{"value": ("gamma",)}],
    }

    assert normalize_for_toon(payload) == {
        "1": ["alpha", "beta"],
        "nested": [{"value": ["gamma"]}],
    }


def test_render_toon_round_trips_payload() -> None:
    payload = {
        "items": [
            {
                "id": "job-1",
                "state": "queued",
                "queue": "agent",
            }
        ],
        "meta": {"count": 1},
    }

    rendered = render_toon(payload)

    assert "items[1" in rendered
    assert decode(rendered) == payload
