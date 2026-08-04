"""Public SDK facet for worker operations."""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING

from xqueue.jobs.models import JobDetail
from xqueue.workers.models import RegisterWorkerInput, WorkerPollResult, WorkerState, WorkerView

if TYPE_CHECKING:
    from xqueue.runtime.composition import Runtime


class Workers:
    """Typed worker operations sharing one owned runtime."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def register(self, payload: RegisterWorkerInput) -> WorkerView:
        self._runtime.ensure_open()
        return self._runtime.worker_actions.register(payload)

    def list(self) -> list[WorkerView]:
        self._runtime.ensure_open()
        return self._runtime.worker_actions.list()

    def running_commands(self) -> dict[str, str]:
        self._runtime.ensure_open()
        return self._runtime.worker_actions.running_commands()

    def set_state(self, worker_id: str, state: WorkerState) -> WorkerView:
        self._runtime.ensure_open()
        return self._runtime.worker_actions.set_state(worker_id, state)

    # ``list`` names this facet's own method inside the class body, so annotations
    # below it must reach the builtin explicitly.
    def claim(self, *, worker_id: str, queues: builtins.list[str], lease_duration_seconds: int) -> JobDetail | None:
        self._runtime.ensure_open()
        return self._runtime.worker_actions.claim(
            worker_id=worker_id,
            queues=queues,
            lease_duration_seconds=lease_duration_seconds,
        )

    def run(
        self,
        payload: RegisterWorkerInput,
        *,
        lease_duration_seconds: int,
        execute_claimed: bool = False,
        continuous: bool = False,
        poll_interval_seconds: float | None = None,
        max_polls: int | None = None,
        default_timeout_seconds: int | None = None,
        cancel_grace_period_seconds: int | None = None,
        retry_delay_seconds: int | None = None,
    ) -> WorkerPollResult:
        self._runtime.ensure_open()
        runner = self._runtime.build_worker_runner(
            default_timeout_seconds=default_timeout_seconds,
            cancel_grace_period_seconds=cancel_grace_period_seconds,
            retry_delay_seconds=retry_delay_seconds,
        )
        if continuous:
            return runner.loop(
                payload,
                lease_duration_seconds=lease_duration_seconds,
                poll_interval_seconds=(
                    self._runtime.config.worker.poll_interval_seconds
                    if poll_interval_seconds is None
                    else poll_interval_seconds
                ),
                execute_claimed=execute_claimed,
                max_polls=max_polls,
            )
        return runner.poll(
            payload,
            lease_duration_seconds=lease_duration_seconds,
            execute_claimed=execute_claimed,
        )
