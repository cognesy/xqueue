"""Stable response envelopes for CLI JSON output."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Structured error payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ListResponse(BaseModel, Generic[T]):
    """Stable envelope for list commands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[T]
    meta: dict[str, Any] | None = None


class DetailResponse(BaseModel, Generic[T]):
    """Stable envelope for detail commands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item: T


class MutationResponse(BaseModel, Generic[T]):
    """Stable envelope for successful mutations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool = True
    item: T


class ErrorResponse(BaseModel):
    """Stable envelope for failures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool = False
    error: ErrorDetail
