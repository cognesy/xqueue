"""Direct-mode worker process supervisor."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Callable, Protocol

from xqueue.adapters.sqlite.session import SessionManager
from xqueue.controller.bootstrap import xqueue_python_command
from xqueue.controller.models import (
    ControllerCommandResult,
    ControllerPoolView,
    ControllerState,
    ControllerStatusView,
    ControllerWorkerView,
)
from xqueue.core.errors import NotFoundError
from xqueue.workers.models import WorkerState
from xqueue.workers.store import WorkerService
from xqueue.workspace.models import ControllerPoolConfig, EffectiveConfig, RestartPolicy


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class ProcessHandle(Protocol):
    """Minimal process interface used by the controller service."""

    # Read-only so subprocess.Popen, whose pid is a plain int, satisfies it.
    @property
    def pid(self) -> int: ...

    def poll(self) -> int | None: ...


class WorkerLauncher(Protocol):
    """Starts one worker child process for a controller slot."""

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        stdout_path: Path,
        stderr_path: Path,
    ) -> ProcessHandle: ...


@dataclass
class WorkerProcessRecord:
    """Tracked child process for one controller-managed worker slot."""

    pool_name: str
    worker_id: str
    process: ProcessHandle
    restart_count: int = 0


class ControllerService:
    """Supervise configured worker pools through child worker processes."""

    def __init__(
        self,
        session_manager: SessionManager,
        worker_service: WorkerService | None = None,
        *,
        launcher: WorkerLauncher | None = None,
        sleep_fn: Callable[[float], None] = sleep,
        clock: Callable[[], datetime] = utc_now,
        python_executable: str = sys.executable,
    ) -> None:
        self._session_manager = session_manager
        self._worker_service = worker_service or WorkerService()
        self._launcher = launcher or self._launch_worker_process
        self._sleep_fn = sleep_fn
        self._clock = clock
        self._python_executable = python_executable

    def run(
        self,
        *,
        controller_id: str,
        config: EffectiveConfig,
        reload_config: Callable[[], EffectiveConfig] | None = None,
        workspace_root: Path,
        use_workspace_instance: bool,
        max_supervision_loops: int | None = None,
        supervision_interval_seconds: float = 0.5,
    ) -> ControllerStatusView:
        current_config = config
        runtime_root = current_config.paths.runtime_root
        runtime_root.mkdir(parents=True, exist_ok=True)
        started_at = self._clock()
        records: dict[str, WorkerProcessRecord] = {}
        state = ControllerState.ACTIVE
        self._clear_control_request(controller_id=controller_id, runtime_root=runtime_root)

        loops = 0
        while True:
            requested_state = self._read_control_request(controller_id=controller_id, runtime_root=runtime_root)
            if requested_state is ControllerState.ACTIVE and state is ControllerState.PAUSED:
                state = ControllerState.ACTIVE
                self._request_worker_state(config=current_config, controller_id=controller_id, state=WorkerState.ACTIVE)
            elif requested_state is ControllerState.PAUSED:
                state = ControllerState.PAUSED
                self._request_worker_state(config=current_config, controller_id=controller_id, state=WorkerState.PAUSED)
            elif requested_state is ControllerState.DRAINING:
                state = ControllerState.DRAINING
                self._request_worker_state(
                    config=current_config, controller_id=controller_id, state=WorkerState.DRAINING
                )
            elif requested_state is ControllerState.STOPPING:
                state = ControllerState.STOPPING
                self._request_worker_state(
                    config=current_config, controller_id=controller_id, state=WorkerState.STOPPED
                )
            elif requested_state is ControllerState.RESTARTING:
                state = ControllerState.RESTARTING
                self._request_worker_state(
                    config=current_config, controller_id=controller_id, state=WorkerState.STOPPED
                )

            if state is ControllerState.ACTIVE:
                self._ensure_pool_processes(
                    records=records,
                    controller_id=controller_id,
                    config=current_config,
                    workspace_root=workspace_root,
                    use_workspace_instance=use_workspace_instance,
                )
            elif state is ControllerState.PAUSED:
                self._request_worker_state(config=current_config, controller_id=controller_id, state=WorkerState.PAUSED)
            elif state is ControllerState.RESTARTING:
                if self._all_processes_exited(records):
                    records.clear()
                    self._clear_control_request(controller_id=controller_id, runtime_root=runtime_root)
                    if reload_config is not None:
                        current_config = reload_config()
                    state = ControllerState.ACTIVE
                    self._ensure_pool_processes(
                        records=records,
                        controller_id=controller_id,
                        config=current_config,
                        workspace_root=workspace_root,
                        use_workspace_instance=use_workspace_instance,
                    )
            elif state in {ControllerState.DRAINING, ControllerState.STOPPING} and self._all_processes_exited(records):
                state = ControllerState.STOPPED

            status = self._build_status(
                controller_id=controller_id,
                config=current_config,
                state=state,
                started_at=started_at,
                records=records,
            )
            self._write_status(status, runtime_root=runtime_root)

            loops += 1
            if max_supervision_loops is not None and loops >= max_supervision_loops and state is ControllerState.ACTIVE:
                state = ControllerState.STOPPING
                self._request_worker_state(
                    config=current_config, controller_id=controller_id, state=WorkerState.STOPPED
                )
            elif state is ControllerState.STOPPED:
                break

            self._sleep_fn(supervision_interval_seconds)

        final_status = self._build_status(
            controller_id=controller_id,
            config=current_config,
            state=ControllerState.STOPPED,
            started_at=started_at,
            records=records,
        )
        self._write_status(final_status, runtime_root=runtime_root)
        return final_status

    def get_status(self, *, controller_id: str, config: EffectiveConfig) -> ControllerStatusView:
        status_path = self._status_path(controller_id=controller_id, runtime_root=config.paths.runtime_root)
        if not status_path.exists():
            return ControllerStatusView(
                controller_id=controller_id,
                state=ControllerState.STOPPED,
                process_id=None,
                config_path=str(config.paths.config_file),
                started_at=None,
                updated_at=self._clock(),
                pools=[
                    ControllerPoolView(
                        name=name,
                        queues=pool.queues,
                        concurrency=pool.concurrency,
                        poll_interval_seconds=pool.poll_interval_seconds or config.worker.poll_interval_seconds,
                        restart_policy=pool.restart_policy.value,
                        default_timeout_seconds=pool.default_timeout_seconds,
                        workers=[],
                    )
                    for name, pool in config.controller.pools.items()
                ],
            )
        payload = json.loads(status_path.read_text())
        return ControllerStatusView.model_validate(payload)

    def request_state(
        self,
        *,
        controller_id: str,
        runtime_root: Path,
        requested_state: ControllerState,
    ) -> ControllerCommandResult:
        runtime_root.mkdir(parents=True, exist_ok=True)
        control_path = self._control_path(controller_id=controller_id, runtime_root=runtime_root)
        control_path.write_text(
            json.dumps(
                {
                    "requested_state": requested_state.value,
                    "updated_at": self._clock().isoformat(),
                },
                indent=2,
            )
        )
        return ControllerCommandResult(
            controller_id=controller_id,
            requested_state=requested_state,
            control_path=str(control_path),
        )

    def _ensure_pool_processes(
        self,
        *,
        records: dict[str, WorkerProcessRecord],
        controller_id: str,
        config: EffectiveConfig,
        workspace_root: Path,
        use_workspace_instance: bool,
    ) -> None:
        for pool_name, pool in config.controller.pools.items():
            for slot_index in range(pool.concurrency):
                worker_id = self._worker_id(controller_id=controller_id, pool_name=pool_name, slot_index=slot_index)
                existing = records.get(worker_id)
                if existing is not None:
                    exit_code = existing.process.poll()
                    if exit_code is None:
                        continue
                    if pool.restart_policy is RestartPolicy.NEVER:
                        continue
                    if pool.restart_policy is RestartPolicy.ON_FAILURE and exit_code == 0:
                        continue
                    stdout_path, stderr_path = self._worker_log_paths(
                        config=config,
                        controller_id=controller_id,
                        worker_id=worker_id,
                    )
                    process = self._launcher(
                        self._build_worker_command(
                            worker_id=worker_id,
                            pool_name=pool_name,
                            pool=pool,
                            config=config,
                            use_workspace_instance=use_workspace_instance,
                        ),
                        cwd=workspace_root,
                        stdout_path=stdout_path,
                        stderr_path=stderr_path,
                    )
                    records[worker_id] = WorkerProcessRecord(
                        pool_name=pool_name,
                        worker_id=worker_id,
                        process=process,
                        restart_count=existing.restart_count + 1,
                    )
                    continue

                stdout_path, stderr_path = self._worker_log_paths(
                    config=config,
                    controller_id=controller_id,
                    worker_id=worker_id,
                )
                process = self._launcher(
                    self._build_worker_command(
                        worker_id=worker_id,
                        pool_name=pool_name,
                        pool=pool,
                        config=config,
                        use_workspace_instance=use_workspace_instance,
                    ),
                    cwd=workspace_root,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                )
                records[worker_id] = WorkerProcessRecord(
                    pool_name=pool_name,
                    worker_id=worker_id,
                    process=process,
                )

    def _all_processes_exited(self, records: dict[str, WorkerProcessRecord]) -> bool:
        return all(record.process.poll() is not None for record in records.values())

    def _request_worker_state(self, *, config: EffectiveConfig, controller_id: str, state: WorkerState) -> None:
        for pool_name, pool in config.controller.pools.items():
            for slot_index in range(pool.concurrency):
                worker_id = self._worker_id(controller_id=controller_id, pool_name=pool_name, slot_index=slot_index)
                with self._session_manager.transaction() as session:
                    try:
                        self._worker_service.set_worker_state(
                            session,
                            worker_id=worker_id,
                            state=state,
                            now=self._clock(),
                            touch_heartbeat=False,
                        )
                    except NotFoundError:
                        continue

    def _build_status(
        self,
        *,
        controller_id: str,
        config: EffectiveConfig,
        state: ControllerState,
        started_at: datetime,
        records: dict[str, WorkerProcessRecord],
    ) -> ControllerStatusView:
        pools: list[ControllerPoolView] = []
        for pool_name, pool in config.controller.pools.items():
            workers = []
            for slot_index in range(pool.concurrency):
                worker_id = self._worker_id(controller_id=controller_id, pool_name=pool_name, slot_index=slot_index)
                record = records.get(worker_id)
                if record is None:
                    continue
                exit_code = record.process.poll()
                workers.append(
                    ControllerWorkerView(
                        worker_id=worker_id,
                        pool_name=pool_name,
                        process_id=record.process.pid,
                        process_state="running" if exit_code is None else "exited",
                        restart_count=record.restart_count,
                        exit_code=exit_code,
                    )
                )
            pools.append(
                ControllerPoolView(
                    name=pool_name,
                    queues=pool.queues,
                    concurrency=pool.concurrency,
                    poll_interval_seconds=pool.poll_interval_seconds or config.worker.poll_interval_seconds,
                    restart_policy=pool.restart_policy.value,
                    default_timeout_seconds=pool.default_timeout_seconds,
                    workers=workers,
                )
            )
        return ControllerStatusView(
            controller_id=controller_id,
            state=state,
            process_id=os.getpid(),
            config_path=str(config.paths.config_file),
            started_at=started_at,
            updated_at=self._clock(),
            pools=pools,
        )

    def _write_status(self, status: ControllerStatusView, *, runtime_root: Path) -> None:
        runtime_root.mkdir(parents=True, exist_ok=True)
        self._status_path(controller_id=status.controller_id, runtime_root=runtime_root).write_text(
            json.dumps(status.model_dump(mode="json"), indent=2)
        )

    def _read_control_request(self, *, controller_id: str, runtime_root: Path) -> ControllerState | None:
        control_path = self._control_path(controller_id=controller_id, runtime_root=runtime_root)
        if not control_path.exists():
            return None
        payload = json.loads(control_path.read_text())
        return ControllerState(payload["requested_state"])

    def _clear_control_request(self, *, controller_id: str, runtime_root: Path) -> None:
        control_path = self._control_path(controller_id=controller_id, runtime_root=runtime_root)
        if control_path.exists():
            control_path.unlink()

    def _build_worker_command(
        self,
        *,
        worker_id: str,
        pool_name: str,
        pool: ControllerPoolConfig,
        config: EffectiveConfig,
        use_workspace_instance: bool,
    ) -> list[str]:
        command = xqueue_python_command(
            self._python_executable,
            "worker",
            "run",
            "--worker-id",
            worker_id,
            "--concurrency",
            "1",
            "--lease-seconds",
            str(pool.lease_seconds),
            "--continuous",
            "--poll-interval-seconds",
            str(pool.poll_interval_seconds or config.worker.poll_interval_seconds),
            "--cancel-grace-period-seconds",
            str(config.worker.cancel_grace_period_seconds),
            "--retry-delay-seconds",
            str(config.worker.retry_delay_seconds),
        )
        command.append("--execute-claimed")
        if pool.default_timeout_seconds is not None:
            command.extend(["--default-timeout-seconds", str(pool.default_timeout_seconds)])
        for queue in pool.queues:
            command.extend(["--queue", queue])
        if use_workspace_instance:
            command.append("--workspace-instance")
        return command

    def _launch_worker_process(
        self,
        command: list[str],
        *,
        cwd: Path,
        stdout_path: Path,
        stderr_path: Path,
    ) -> subprocess.Popen[bytes]:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        with stdout_path.open("ab") as stdout_handle, stderr_path.open("ab") as stderr_handle:
            return subprocess.Popen(
                command,
                cwd=str(cwd),
                stdout=stdout_handle,
                stderr=stderr_handle,
            )

    def _worker_id(self, *, controller_id: str, pool_name: str, slot_index: int) -> str:
        return f"controller-{controller_id}-{pool_name}-{slot_index}"

    def _worker_log_paths(self, *, config: EffectiveConfig, controller_id: str, worker_id: str) -> tuple[Path, Path]:
        controller_log_root = config.paths.log_root / "controller" / controller_id
        return (
            controller_log_root / f"{worker_id}.stdout.log",
            controller_log_root / f"{worker_id}.stderr.log",
        )

    def _status_path(self, *, controller_id: str, runtime_root: Path) -> Path:
        return runtime_root / f"controller-{controller_id}.status.json"

    def _control_path(self, *, controller_id: str, runtime_root: Path) -> Path:
        return runtime_root / f"controller-{controller_id}.control.json"
