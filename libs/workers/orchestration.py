"""Worker orchestration and polling use cases."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import sleep

from sqlalchemy.orm import Session
from xqueue.adapters.filesystem.metrics import MetricsService
from xqueue.adapters.sqlite.session import SessionManager
from xqueue.jobs.models import JobDetail, JobState
from xqueue.jobs.store import JobService
from xqueue.runtime.action_logging import log_action
from xqueue.workers.attempts import AttemptService
from xqueue.workers.models import (
    AttemptLogPaths,
    ProcessExecutionResult,
    RegisterWorkerInput,
    ShellExecutionRequest,
    WorkerPollResult,
    WorkerState,
    WorkerView,
)
from xqueue.workers.operation_logs import JobOperationLogService
from xqueue.workers.ports import ProcessRunnerPort
from xqueue.workers.store import WorkerService


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
            "worker_id": result.id,
            "worker_state": result.state.value,
        },
    )
    def __call__(self, payload: RegisterWorkerInput) -> WorkerView:
        with self._session_manager.transaction() as session:
            item = self._worker_service.register_worker(session, payload=payload, now=self._clock())
        return item


class ListWorkersAction:
    """Return persisted worker views."""

    def __init__(self, session_manager: SessionManager, worker_service: WorkerService) -> None:
        self._session_manager = session_manager
        self._worker_service = worker_service

    @log_action(
        "list_workers",
        result_getter=lambda result: {"item_count": len(result)},
    )
    def __call__(self) -> list[WorkerView]:
        with self._session_manager.session() as session:
            items = self._worker_service.list_workers(session)
        return items


class RunningWorkerCommandsAction:
    """Return current command text keyed by running worker id."""

    def __init__(self, session_manager: SessionManager, worker_service: WorkerService) -> None:
        self._session_manager = session_manager
        self._worker_service = worker_service

    def __call__(self) -> dict[str, str]:
        with self._session_manager.session() as session:
            return self._worker_service.running_worker_commands(session)


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
        result_getter=lambda result: {"worker_id": result.id, "worker_state": result.state.value},
    )
    def __call__(self, worker_id: str, state: WorkerState) -> WorkerView:
        with self._session_manager.transaction() as session:
            item = self._worker_service.set_worker_state(
                session,
                worker_id=worker_id,
                state=state,
                now=self._clock(),
            )
        return item


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
            "claimed_job_id": None if result is None else result.id,
            "claimed_job_state": None if result is None else result.state.value,
        },
    )
    def __call__(self, *, worker_id: str, queues: list[str], lease_duration_seconds: int) -> JobDetail | None:
        now = self._clock()
        with self._session_manager.transaction() as session:
            item = self._worker_service.claim_next_job(
                session,
                worker_id=worker_id,
                queues=queues,
                now=now,
                lease_expires_at=now + timedelta(seconds=lease_duration_seconds),
            )
        return item


class RunWorkerAction:
    """Perform one worker poll iteration: register, heartbeat, and claim."""

    def __init__(
        self,
        session_manager: SessionManager,
        worker_service: WorkerService,
        job_service: JobService,
        attempt_service: AttemptService,
        execution_service: ProcessRunnerPort,
        *,
        log_root: Path,
        metrics: MetricsService,
        default_timeout_seconds: int = 3600,
        cancel_grace_period_seconds: int = 10,
        retry_delay_seconds: int = 5,
        clock: Callable[[], datetime] = utc_now,
        operation_logs: JobOperationLogService | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._worker_service = worker_service
        self._job_service = job_service
        self._attempt_service = attempt_service
        self._execution_service = execution_service
        self._log_root = log_root
        self._default_timeout_seconds = default_timeout_seconds
        self._cancel_grace_period_seconds = cancel_grace_period_seconds
        self._retry_delay_seconds = retry_delay_seconds
        self._clock = clock
        self._metrics = metrics
        self._operation_logs = operation_logs or JobOperationLogService()

    @log_action(
        "run_worker",
        context_getter=lambda self, payload, *, lease_duration_seconds, execute_claimed=False: {
            "worker_id": payload.worker_id,
            "queues": payload.queues,
            "lease_duration_seconds": lease_duration_seconds,
            "execute_claimed": execute_claimed,
        },
        result_getter=lambda result: {
            "worker_id": result.worker.id,
            "worker_state": result.worker.state.value,
            "claimed_job_id": None if result.claimed_job is None else result.claimed_job.id,
            "claimed_job_state": None if result.claimed_job is None else result.claimed_job.state.value,
        },
    )
    def __call__(
        self,
        payload: RegisterWorkerInput,
        *,
        lease_duration_seconds: int,
        execute_claimed: bool = False,
    ) -> WorkerPollResult:
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
        return WorkerPollResult(
            worker=worker,
            claimed_job=claimed_job,
        )

    def _execute_claimed_job(
        self,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
        lease_duration_seconds: int,
    ) -> JobDetail:
        with self._session_manager.session() as session:
            job = self._job_service.get_job(session, job_id=job_id)

        log_paths = self._execution_service.build_attempt_log_paths(
            log_root=self._log_root,
            job_id=job_id,
            attempt_number=job.attempt_count + 1,
        )
        correlation = self._operation_logs.correlation_from_env(job.env)
        self._operation_logs.append(
            path=log_paths.event_log_path,
            event="job.claimed",
            job_id=job.id,
            queue=job.queue,
            worker_id=worker_id,
            attempt_number=job.attempt_count + 1,
            command=job.command,
            cwd=job.cwd,
            stdout_path=log_paths.stdout_path,
            stderr_path=log_paths.stderr_path,
            correlation=correlation,
            timestamp=now,
        )

        with self._session_manager.transaction() as session:
            started_attempt = self._attempt_service.start_attempt(
                session,
                job_id=job_id,
                worker_id=worker_id,
                log_paths=AttemptLogPaths(
                    stdout_path=log_paths.stdout_path,
                    stderr_path=log_paths.stderr_path,
                    event_log_path=log_paths.event_log_path,
                ),
                now=now,
            )
        self._operation_logs.append(
            path=log_paths.event_log_path,
            event="job.started",
            job_id=job.id,
            queue=job.queue,
            worker_id=worker_id,
            attempt_id=started_attempt.id,
            attempt_number=started_attempt.attempt_number,
            command=job.command,
            cwd=job.cwd,
            stdout_path=started_attempt.stdout_path,
            stderr_path=started_attempt.stderr_path,
            correlation=correlation,
            timestamp=started_attempt.started_at,
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
            finalized_job = self._attempt_service.finalize_attempt(
                session,
                attempt_id=started_attempt.id,
                result=result,
                retry_delay_seconds=self._retry_delay_seconds,
            )
        duration_seconds = (result.finished_at - result.started_at).total_seconds()
        outcome = self._operation_outcome(result=result, job_state=finalized_job.state.value)
        self._operation_logs.append(
            path=log_paths.event_log_path,
            event="job.finished",
            job_id=job.id,
            queue=job.queue,
            worker_id=worker_id,
            attempt_id=started_attempt.id,
            attempt_number=started_attempt.attempt_number,
            command=job.command,
            cwd=job.cwd,
            pid=result.process_id,
            exit_code=result.exit_code,
            outcome=outcome,
            duration_seconds=duration_seconds,
            stdout_path=result.stdout_path,
            stderr_path=result.stderr_path,
            correlation=correlation,
            timestamp=result.finished_at,
        )
        self._operation_logs.append(
            path=log_paths.event_log_path,
            event=self._terminal_event(result=result, job_state=finalized_job.state.value),
            job_id=job.id,
            queue=job.queue,
            worker_id=worker_id,
            attempt_id=started_attempt.id,
            attempt_number=started_attempt.attempt_number,
            command=job.command,
            cwd=job.cwd,
            pid=result.process_id,
            exit_code=result.exit_code,
            outcome=outcome,
            duration_seconds=duration_seconds,
            stdout_path=result.stdout_path,
            stderr_path=result.stderr_path,
            correlation=correlation,
            timestamp=result.finished_at,
        )
        return finalized_job

    def _operation_outcome(self, *, result: ProcessExecutionResult, job_state: str) -> str:
        if result.canceled:
            return "canceled"
        if result.timed_out:
            return "retry_scheduled" if job_state == JobState.RETRY_SCHEDULED.value else "timed_out"
        if result.exit_code == 0:
            return "succeeded"
        return "retry_scheduled" if job_state == JobState.RETRY_SCHEDULED.value else "failed"

    def _terminal_event(self, *, result: ProcessExecutionResult, job_state: str) -> str:
        outcome = self._operation_outcome(result=result, job_state=job_state)
        if outcome == "retry_scheduled":
            return "job.retry_scheduled"
        return f"job.{outcome}"

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

        def renew(session: Session) -> bool:
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
            "worker_id": result.worker.id,
            "worker_state": result.worker.state.value,
            "claimed_job_id": None if result.claimed_job is None else result.claimed_job.id,
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
    ) -> WorkerPollResult:
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
    ) -> WorkerPollResult:
        polls = 0
        last_result = self._run_worker_action(
            payload,
            lease_duration_seconds=lease_duration_seconds,
            execute_claimed=execute_claimed,
        )
        polls += 1

        while True:
            worker_state = last_result.worker.state
            if worker_state is WorkerState.STOPPED:
                return last_result
            if worker_state is WorkerState.DRAINING and last_result.claimed_job is None:
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
    ) -> WorkerPollResult:
        polls = 0
        last_result: WorkerPollResult | None = None
        active_futures: set[Future[WorkerPollResult]] = set()

        with ThreadPoolExecutor(
            max_workers=payload.concurrency,
            thread_name_prefix=f"xq-worker-{payload.worker_id}",
        ) as executor:
            while True:
                worker_state = WorkerState.ACTIVE if last_result is None else last_result.worker.state

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
                    if last_result is not None and last_result.worker.state in {
                        WorkerState.STOPPED,
                        WorkerState.DRAINING,
                    }:
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

                worker_state = last_result.worker.state
                if max_polls is not None and polls >= max_polls and not active_futures:
                    return last_result
                if worker_state is WorkerState.STOPPED and not active_futures:
                    return last_result
                if worker_state is WorkerState.DRAINING and not active_futures:
                    return last_result
                if last_result.claimed_job is None and not active_futures:
                    self._sleep_fn(poll_interval_seconds)

    def _run_worker_slot(
        self,
        payload: RegisterWorkerInput,
        *,
        lease_duration_seconds: int,
    ) -> WorkerPollResult:
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
