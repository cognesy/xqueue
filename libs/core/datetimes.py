"""Datetime normalization helpers shared by capabilities."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import overload


@overload
def ensure_utc(value: datetime) -> datetime: ...


@overload
def ensure_utc(value: None) -> None: ...


def ensure_utc(value: datetime | None) -> datetime | None:
    """Attach UTC to naive datetimes returned by SQLite."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
