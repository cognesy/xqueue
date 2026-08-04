"""Shared action-level structured logging at the runtime boundary."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from time import perf_counter
from typing import Any, ParamSpec, TypeVar

import structlog
from xqueue.core.errors import XqueueError

P = ParamSpec("P")
R = TypeVar("R")


def log_action(
    action_name: str,
    *,
    # Neither getter can name the decorated signature: both are written before
    # the function they describe exists. Typing them against P or R would bind
    # those variables here and force every decorated action to match the getter
    # instead of the other way round. Metadata extraction is untyped by
    # construction and already guarded by _safe_metadata.
    context_getter: Callable[..., dict[str, Any] | None] | None = None,
    result_getter: Callable[[Any], dict[str, Any] | None] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Log action start, success, and failure through structlog."""

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Actions bind and emit; configuring process-global logging is the
            # entry point's job, not something a library call does as a side effect.
            logger = structlog.get_logger("xqueue.action").bind(action=action_name)
            context = _safe_metadata(lambda: context_getter(*args, **kwargs) if context_getter else None)
            started_at = perf_counter()
            logger.info("action.started", **context)

            try:
                result = fn(*args, **kwargs)
            except XqueueError as exc:
                logger.warning(
                    "action.failed",
                    duration_ms=_duration_ms(started_at),
                    error_code=exc.code,
                    error_message=exc.message,
                    **context,
                )
                raise
            except Exception:
                logger.exception(
                    "action.failed",
                    duration_ms=_duration_ms(started_at),
                    **context,
                )
                raise

            result_metadata = _safe_metadata(lambda: result_getter(result) if result_getter else None)
            success_metadata = dict(context)
            success_metadata.update(result_metadata)
            success_metadata["duration_ms"] = _duration_ms(started_at)
            logger.info(
                "action.succeeded",
                **success_metadata,
            )
            return result

        return wrapper

    return decorator


def _safe_metadata(factory: Callable[[], dict[str, Any] | None]) -> dict[str, Any]:
    try:
        return factory() or {}
    except Exception:
        return {}


def _duration_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)
