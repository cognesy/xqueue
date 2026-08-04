"""Public SDK facet for queue operations."""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING

from xqueue.queues.models import PurgeJobsResult, QueueStatsView, QueueView

if TYPE_CHECKING:
    from xqueue.runtime.composition import Runtime


class Queues:
    """Typed queue operations sharing one owned runtime."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def list(self) -> list[QueueView]:
        self._runtime.ensure_open()
        return self._runtime.queue_actions.list()

    # ``list`` names this facet's own method inside the class body, so annotations
    # below it must reach the builtin explicitly.
    def stats(self) -> builtins.list[QueueStatsView]:
        self._runtime.ensure_open()
        return self._runtime.queue_actions.stats()

    def pause(self, queue: str) -> QueueView:
        self._runtime.ensure_open()
        return self._runtime.queue_actions.pause(queue)

    def resume(self, queue: str) -> QueueView:
        self._runtime.ensure_open()
        return self._runtime.queue_actions.resume(queue)

    def purge(self, queue: str) -> PurgeJobsResult:
        self._runtime.ensure_open()
        return self._runtime.queue_actions.purge(queue)
