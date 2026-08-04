"""Stable response envelopes owned by the CLI channel."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PayloadConvertible(BaseModel):
    """Base model for values that can be rendered by the CLI output layer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable payload for structured formats."""
        return self.model_dump(mode="json")

    def jsonl_items(self) -> list[Any] | None:
        """Return JSONL rows when the response has a natural item stream."""
        return None


class ErrorDetail(BaseModel):
    """Structured error payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ListResponse(PayloadConvertible, Generic[T]):
    """Stable envelope for list commands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[T]
    meta: dict[str, Any] | None = None

    def jsonl_items(self) -> list[Any] | None:
        """Emit list items as JSONL rows."""
        return list(self.items)


class DetailResponse(PayloadConvertible, Generic[T]):
    """Stable envelope for detail commands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item: T


class MutationResponse(PayloadConvertible, Generic[T]):
    """Stable envelope for successful mutations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool = True
    item: T


class ErrorResponse(PayloadConvertible):
    """Stable envelope for failures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool = False
    error: ErrorDetail
