"""CLI-owned TOON rendering for structured responses."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from toon import encode

TOON_OPTIONS = {
    "indent": 2,
    "delimiter": ",",
}


def normalize_for_toon(value: Any) -> Any:
    """Normalize Python containers into TOON-friendly primitives."""
    if isinstance(value, Mapping):
        return {str(key): normalize_for_toon(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [normalize_for_toon(item) for item in value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_for_toon(item) for item in value]
    return value


def render_toon(value: Any) -> str:
    """Render one payload as TOON."""
    return encode(normalize_for_toon(value), options=TOON_OPTIONS)


__all__ = ["TOON_OPTIONS", "normalize_for_toon", "render_toon"]
