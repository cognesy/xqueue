"""Worker lifecycle and claim actions."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import sleep

from libs.actions.logging import log_action
from libs.domain.errors import RuntimeExecutionError
from libs.domain.models import AttemptLogPaths, RegisterWorkerInput, ShellExecutionRequest, WorkerPollResult, WorkerState
from libs.domain.responses import DetailResponse, ListResponse, MutationResponse
from libs.services.attempts import AttemptService
from libs.services.database import SessionManager
from libs.services.execution import CommandExecutionService
from libs.services.jobs import JobService
from libs.services.metrics import MetricsService
from libs.services.workers import WorkerService


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class RegisterWorkerAction:
    """Register or refresh a worker record."""

    def __init__(
        self,
        session_manager: SessionManager,
        worker_service: WorkerService,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._worker_service = worker_service
        self._clock = clock

    @log_action(
        "register_worker",
        context_getter=lambda self, payload: {
            "worker_id": payload.worker_id,
            "queues": payload.queues,
            "concurrency": payload.concurrency,
        },
        result_getter=lambda result: {
            "worker_id": result.item.id,
            "worker_state": result.item.state.value,
        },
    )
    def __call__(self, payload: RegisterWorkerInput) -> MutationResponse:
        with self._session_manager.transaction() as session:
            item = self._worker_service.register_worker(session, payload=payload, now=self._clock())
        return MutationResponse(item=item)


class ListWorkersAction:
    """Return persisted worker views."""

    def __init__(self, session_manager: SessionManager, worker_service: WorkerService) -> None:
        self._session_manager = session_manager
        self._worker_service = worker_service

    @log_action(
        "list_workers",
        result_getter=lambda result: {"item_count": len(result.items)},
    )
    def __call__(self) -> ListResponse:
        with self._session_manager.session() as session:
            items = self._worker_service.list_workers(session)
        return ListResponse(items=items)


class SetWorkerStateAction:
    """Persist an operator-requested worker state change."""

    def __init__(
        self,
        session_manager: SessionManager,
        worker_service: WorkerService,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._worker_service = worker_service
        self._clock = clock

    @log_action(
        "set_worker_state",
        context_getter=lambda self, worker_id, state: {"worker_id": worker_id, "requested_state": state.value},
        result_getter=lambda result: {"worker_id": result.item.id, "worker_state": result.item.state.value},
    )
    def __call__(self, worker_id: str, state: WorkerState) -> MutationResponse:
        with self._session_manager.transaction() as session:
            item = self._worker_service.set_worker_state(
                session,
                worker_id=worker_id,
                state=state,
                now=self._clock(),
            )
        return MutationResponse(item=item)


class ClaimNextJobAction:
    """Claim one runnable job for a worker, if available."""

    def __init__(
        self,
        session_manager: SessionManager,
        worker_service: WorkerService,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session_manager = session_manager
        self._worker_service = worker_service
        self._clock = clock

    @log_action(
        "claim_next_job",
        context_getter=lambda self, *, worker_id, queues, lease_duration_seconds: {
            "worker_id": worker_id,
            "queues": queues,
            "lease_duration_seconds": lease_duration_seconds,
        },
        result_getter=lambda result: {
            "claimed_job_id": None if result.item is None else result.item.id,
            "claimed_job_state": None if result.item is None else result.item.state.value,
        },
    )
    def __call__(self, *, worker_id: str, queues: list[str], lease_duration_seconds: int) -> DetailResponse:
        now = self._clock()
        with self._session_manager.transaction() as session:
            item = self._worker_service.claim_next_job(
                session,
                worker_id=worker_id,
                queues=queues,
                now=now,
                lease_expires_at=now + timedelta(seconds=lease_duration_seconds),
            )
        return DetailResponse(item=item)


class RunWorkerAction:
    """Perform one worker poll iteration: register, heartbeat, and claim."""

    def __init__(
        self,
        session_manager: SessionManager,
        worker_service: WorkerService,
        job_service: JobService | None = None,
        attempt_service: AttemptService | None = None,
        execution_service: CommandExecutionService | None = None,
        *,
        log_root: Path | None = None,
        default_timeout_seconds: int = 3600,
        cancel_grace_period_seconds: int = 10,
        retry_delay_seconds: int = 5,
        clock: Callable[[], datetime] = utc_now,
        metrics: MetricsService | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._worker_service = worker_service
        self._job_service = job_service or JobService()
        self._attempt_service = attempt_service
        self._execution_service = execution_service
        self._log_root = log_root
        self._default_timeout_seconds = default_timeout_seconds
        self._cancel_grace_period_seconds = cancel_grace_period_seconds
        self._retry_delay_seconds = retry_delay_seconds
        self._clock = clock
        self._metrics = metrics or MetricsService()

    @log_action(
        "run_worker",
        context_getter=lambda self, payload, *, lease_duration_seconds, execute_claimed=False: {
            "worker_id": payload.worker_id,
            "queues": payload.queues,
            "lease_duration_seconds": lease_duration_seconds,
            "execute_claimed": execute_claimed,
        },
        result_getter=lambda result: {
            "worker_id": result.item.worker.id,
            "worker_state": result.item.worker.state.value,
            "claimed_job_id": None if result.item.claimed_job is None else result.item.claimed_job.id,
            "claimed_job_state": None if result.item.claimed_job is None else result.item.claimed_job.state.value,
        },
    )
    def __call__(
        self,
        payload: RegisterWorkerInput,
        *,
        lease_duration_seconds: int,
        execute_claimed: bool = False,
    ) -> DetailResponse:
        self._metrics.increment("worker.polls")
        now = self._clock()
        with self._session_manager.transaction() as session:
            worker = self._worker_service.register_worker(session, payload=payload, now=now)
            claimed_job = self._worker_service.claim_next_job(
                session,
                worker_id=payload.worker_id,
                queues=payload.queues,
                now=now,
                lease_expires_at=now + timedelta(seconds=lease_duration_seconds),
            )

        if claimed_job is not None:
            self._metrics.increment("jobs.claimed")
        if claimed_job is not None and execute_claimed:
            self._metrics.increment("jobs.executed")
            claimed_job = self._execute_claimed_job(
                job_id=claimed_job.id,
                worker_id=payload.worker_id,
                now=now,
                lease_duration_seconds=lease_duration_seconds,
            )
            with self._session_manager.transaction() as session:
                worker = self._worker_service.heartbeat_worker(
                    session,
                    worker_id=payload.worker_id,
                    now=self._clock(),
                )

        if claimed_job is not None and execute_claimed:
            self._metrics.increment(f"jobs.{claimed_job.state.value}")
        return DetailResponse(
            item=WorkerPollResult(
                worker=worker,
                claimed_job=claimed_job,
            )
        )

    def _execute_claimed_job(
        self,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
        lease_duration_seconds: int,
    ):
        if self._attempt_service is None or self._execution_service is None or self._log_root is None:
            raise RuntimeExecutionError("worker execution dependencies are not configured")

        with self._session_manager.session() as session:
            job = self._job_service.get_job(session, job_id=job_id)

        log_paths = self._execution_service.build_attempt_log_paths(
            log_root=self._log_root,
            job_id=job_id,
            attempt_number=job.attempt_count + 1,
        )

        with self._session_manager.transaction() as session:
            started_attempt = self._attempt_service.start_attempt(
                session,
                job_id=job_id,
                worker_id=worker_id,
                log_paths=AttemptLogPaths(
                    stdout_path=log_paths.stdout_path,
                    stderr_path=log_paths.stderr_path,
                ),
                now=now,
            )

        result = self._execution_service.run(
            request=ShellExecutionRequest(
                command=job.command,
                cwd=job.cwd,
                env=job.env,
                shell=job.shell,
                timeout_seconds=job.timeout_seconds or self._default_timeout_seconds,
            ),
            log_paths=log_paths,
            cancel_grace_period_seconds=self._cancel_grace_period_seconds,
            should_cancel=lambda: self._is_cancel_requested(job_id),
            heartbeat_interval_seconds=self._lease_heartbeat_interval_seconds(lease_duration_seconds),
            on_heartbeat=lambda: self._heartbeat_running_job(
                job_id=job_id,
                worker_id=worker_id,
                lease_duration_seconds=lease_duration_seconds,
            ),
        )

        with self._session_manager.transaction() as session:
            return self._attempt_service.finalize_attempt(
                session,
                attempt_id=started_attempt.id,
                result=result,
                retry_delay_seconds=self._retry_delay_seconds,
            )

    def _is_cancel_requested(self, job_id: str) -> bool:
        with self._session_manager.session() as session:
            return self._job_service.is_cancel_requested(session, job_id=job_id)

    def _heartbeat_running_job(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_duration_seconds: int,
    ) -> bool:
        now = self._clock()

        def renew(session) -> bool:
            renewed = self._worker_service.renew_job_lease(
                session,
                job_id=job_id,
                worker_id=worker_id,
                lease_expires_at=now + timedelta(seconds=lease_duration_seconds),
            )
            if renewed:
                self._worker_service.heartbeat_worker(
                    session,
                    worker_id=worker_id,
                    now=now,
                )
            return renewed

        return self._session_manager.run_in_transaction(renew)

    def _lease_heartbeat_interval_seconds(self, lease_duration_seconds: int) -> float:
        return max(0.5, lease_duration_seconds / 2)


class RunWorkerLoopAction:
    """Run a long-lived worker loop for direct mode or controller supervision."""

    def __init__(
        self,
        run_worker_action: RunWorkerAction,
        *,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        self._run_worker_action = run_worker_action
        self._sleep_fn = sleep_fn

    @log_action(
        "run_worker_loop",
        context_getter=lambda self, payload, *, lease_duration_seconds, poll_interval_seconds, execute_claimed=False, max_polls=None: {
            "worker_id": payload.worker_id,
            "queues": payload.queues,
            "lease_duration_seconds": lease_duration_seconds,
            "poll_interval_seconds": poll_interval_seconds,
            "execute_claimed": execute_claimed,
            "max_polls": max_polls,
        },
        result_getter=lambda result: {
            "worker_id": result.item.worker.id,
            "worker_state": result.item.worker.state.value,
            "claimed_job_id": None if result.item.claimed_job is None else result.item.claimed_job.id,
        },
    )
    def __call__(
        self,
        payload: RegisterWorkerInput,
        *,
        lease_duration_seconds: int,
        poll_interval_seconds: float,
        execute_claimed: bool = False,
        max_polls: int | None = None,
    ) -> DetailResponse:
        if execute_claimed and payload.concurrency > 1:
            return self._run_concurrent_slots(
                payload,
                lease_duration_seconds=lease_duration_seconds,
                poll_interval_seconds=poll_interval_seconds,
                max_polls=max_polls,
            )

        return self._run_sequential(
            payload,
            lease_duration_seconds=lease_duration_seconds,
            poll_interval_seconds=poll_interval_seconds,
            execute_claimed=execute_claimed,
            max_polls=max_polls,
        )

    def _run_sequential(
        self,
        payload: RegisterWorkerInput,
        *,
        lease_duration_seconds: int,
        poll_interval_seconds: float,
        execute_claimed: bool,
        max_polls: int | None,
    ) -> DetailResponse:
        polls = 0
        last_result = self._run_worker_action(
            payload,
            lease_duration_seconds=lease_duration_seconds,
            execute_claimed=execute_claimed,
        )
        polls += 1

        while True:
            worker_state = last_result.item.worker.state
            if worker_state is WorkerState.STOPPED:
                return last_result
            if worker_state is WorkerState.DRAINING and last_result.item.claimed_job is None:
                return last_result
            if max_polls is not None and polls >= max_polls:
                return last_result

            self._sleep_fn(poll_interval_seconds)
            last_result = self._run_worker_action(
                payload,
                lease_duration_seconds=lease_duration_seconds,
                execute_claimed=execute_claimed,
            )
            polls += 1

    def _run_concurrent_slots(
        self,
        payload: RegisterWorkerInput,
        *,
        lease_duration_seconds: int,
        poll_interval_seconds: float,
        max_polls: int | None,
    ) -> DetailResponse:
        polls = 0
        last_result: DetailResponse | None = None
        active_futures: set[Future[DetailResponse]] = set()

        with ThreadPoolExecutor(
            max_workers=payload.concurrency,
            thread_name_prefix=f"xq-worker-{payload.worker_id}",
        ) as executor:
            while True:
                worker_state = WorkerState.ACTIVE if last_result is None else last_result.item.worker.state

                if worker_state in {WorkerState.ACTIVE, WorkerState.PAUSED}:
                    target_slots = payload.concurrency if worker_state is WorkerState.ACTIVE else 1
                    while len(active_futures) < target_slots and self._can_schedule_more(
                        polls=polls,
                        active_count=len(active_futures),
                        max_polls=max_polls,
                    ):
                        active_futures.add(
                            executor.submit(
                                self._run_worker_slot,
                                payload,
                                lease_duration_seconds=lease_duration_seconds,
                            )
                        )

                if not active_futures:
                    if last_result is not None and last_result.item.worker.state in {WorkerState.STOPPED, WorkerState.DRAINING}:
                        return last_result
                    if last_result is not None and max_polls is not None and polls >= max_polls:
                        return last_result
                    self._sleep_fn(poll_interval_seconds)
                    continue

                done, _ = wait(
                    active_futures,
                    timeout=poll_interval_seconds,
                    return_when=FIRST_COMPLETED,
                )
                if not done:
                    continue

                for future in done:
                    active_futures.remove(future)
                    last_result = future.result()
                    polls += 1

                if last_result is None:
                    continue

                worker_state = last_result.item.worker.state
                if max_polls is not None and polls >= max_polls and not active_futures:
                    return last_result
                if worker_state is WorkerState.STOPPED and not active_futures:
                    return last_result
                if worker_state is WorkerState.DRAINING and not active_futures:
                    return last_result
                if last_result.item.claimed_job is None and not active_futures:
                    self._sleep_fn(poll_interval_seconds)

        raise RuntimeExecutionError("worker loop terminated without a result")

    def _run_worker_slot(
        self,
        payload: RegisterWorkerInput,
        *,
        lease_duration_seconds: int,
    ) -> DetailResponse:
        return self._run_worker_action(
            payload,
            lease_duration_seconds=lease_duration_seconds,
            execute_claimed=True,
        )

    def _can_schedule_more(
        self,
        *,
        polls: int,
        active_count: int,
        max_polls: int | None,
    ) -> bool:
        if max_polls is None:
            return True
        return polls + active_count < max_polls
