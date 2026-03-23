"""Datetime normalization helpers for SQLite-backed values."""

from __future__ import annotations

from datetime import UTC, datetime


def ensure_utc(value: datetime | None) -> datetime | None:
    """Attach UTC to naive datetimes returned by SQLite."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
