from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path

from libs.actions.controller import RunControllerAction
from libs.domain.config import ControllerConfig, ControllerPoolConfig, EffectiveConfig, QueueConfig, RestartPolicy, RuntimePaths, WorkerDefaults
from libs.domain.models import ControllerState
from libs.infra.database import create_session_factory, create_sqlite_engine
from libs.infra.models import Base, WorkerModel
from libs.services.controller import ControllerService
from libs.services.database import SessionManager
from libs.services.datetimes import ensure_utc
from libs.services.workers import WorkerService


def test_run_controller_action_restarts_failed_pool_worker(tmp_path: Path) -> None:
    database_path = tmp_path / "controller.db"
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    launch_calls: list[list[str]] = []
    process_ids = count(1000)

    class FakeProcess:
        def __init__(self) -> None:
            self.pid = next(process_ids)

        def poll(self) -> int | None:
            return 1

    def launcher(command: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path):
        launch_calls.append(command)
        return FakeProcess()

    config = EffectiveConfig(
        paths=RuntimePaths(
            config_file=tmp_path / "config.yaml",
            state_root=tmp_path / "state",
            runtime_root=tmp_path / "run",
            log_root=tmp_path / "logs",
            database_path=database_path,
        ),
        queue=QueueConfig(),
        worker=WorkerDefaults(),
        controller=ControllerConfig(
            pools={
                "agents": ControllerPoolConfig(
                    queues=["agent"],
                    concurrency=1,
                    restart_policy=RestartPolicy.ON_FAILURE,
                )
            }
        ),
    )

    action = RunControllerAction(
        ControllerService(
            SessionManager(session_factory),
            WorkerService(),
            launcher=launcher,
            sleep_fn=lambda _: None,
        )
    )

    result = action(
        controller_id="default",
        config=config,
        workspace_root=tmp_path,
        use_workspace_instance=False,
        max_supervision_loops=3,
    )

    assert result.item.state == ControllerState.STOPPED
    assert len(launch_calls) >= 2
    assert result.item.pools[0].workers[0].restart_count >= 1
    assert (tmp_path / "run" / "controller-default.status.json").exists()


def test_run_controller_action_reloads_config_after_restart_request(tmp_path: Path) -> None:
    database_path = tmp_path / "controller.db"
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    launch_calls: list[list[str]] = []
    sleep_calls = 0

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self.pid = pid

        def poll(self) -> int | None:
            return 0

    def launcher(command: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path):
        launch_calls.append(command)
        return FakeProcess(1000 + len(launch_calls))

    initial_config = EffectiveConfig(
        paths=RuntimePaths(
            config_file=tmp_path / "config.yaml",
            state_root=tmp_path / "state",
            runtime_root=tmp_path / "run",
            log_root=tmp_path / "logs",
            database_path=database_path,
        ),
        queue=QueueConfig(),
        worker=WorkerDefaults(),
        controller=ControllerConfig(
            pools={
                "agents": ControllerPoolConfig(
                    queues=["agent"],
                    concurrency=1,
                    restart_policy=RestartPolicy.ON_FAILURE,
                )
            }
        ),
    )
    reloaded_config = initial_config.model_copy(
        update={
            "controller": ControllerConfig(
                pools={
                    "agents": ControllerPoolConfig(
                        queues=["agent", "maintenance"],
                        concurrency=2,
                        restart_policy=RestartPolicy.ON_FAILURE,
                    )
                }
            )
        }
    )

    def sleep_and_request_restart(_: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 1:
            service.request_state(
                controller_id="default",
                runtime_root=initial_config.paths.runtime_root,
                requested_state=ControllerState.RESTARTING,
            )

    service = ControllerService(
        SessionManager(session_factory),
        WorkerService(),
        launcher=launcher,
        sleep_fn=sleep_and_request_restart,
    )
    action = RunControllerAction(service)

    result = action(
        controller_id="default",
        config=initial_config,
        reload_config=lambda: reloaded_config,
        workspace_root=tmp_path,
        use_workspace_instance=False,
        max_supervision_loops=2,
    )

    assert result.item.state == ControllerState.STOPPED
    assert len(launch_calls) == 3
    assert launch_calls[0].count("--queue") == 1
    assert launch_calls[1].count("--queue") == 2
    assert launch_calls[2].count("--queue") == 2


def test_run_controller_action_surfaces_pause_intake_and_resume(tmp_path: Path) -> None:
    database_path = tmp_path / "controller.db"
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    launch_calls: list[list[str]] = []
    status_states: list[ControllerState] = []
    should_exit = False

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self.pid = pid

        def poll(self) -> int | None:
            return 0 if should_exit else None

    def launcher(command: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path):
        launch_calls.append(command)
        return FakeProcess(1000 + len(launch_calls))

    config = EffectiveConfig(
        paths=RuntimePaths(
            config_file=tmp_path / "config.yaml",
            state_root=tmp_path / "state",
            runtime_root=tmp_path / "run",
            log_root=tmp_path / "logs",
            database_path=database_path,
        ),
        queue=QueueConfig(),
        worker=WorkerDefaults(),
        controller=ControllerConfig(
            pools={
                "agents": ControllerPoolConfig(
                    queues=["agent"],
                    concurrency=1,
                    restart_policy=RestartPolicy.ON_FAILURE,
                )
            }
        ),
    )

    sleep_calls = 0

    def sleep_and_drive(_: float) -> None:
        nonlocal sleep_calls, should_exit
        sleep_calls += 1
        status_states.append(service.get_status(controller_id="default", config=config).state)
        if sleep_calls == 1:
            service.request_state(
                controller_id="default",
                runtime_root=config.paths.runtime_root,
                requested_state=ControllerState.PAUSED,
            )
        elif sleep_calls == 2:
            status_states.append(service.get_status(controller_id="default", config=config).state)
            service.request_state(
                controller_id="default",
                runtime_root=config.paths.runtime_root,
                requested_state=ControllerState.ACTIVE,
            )
        elif sleep_calls == 3:
            status_states.append(service.get_status(controller_id="default", config=config).state)
            service.request_state(
                controller_id="default",
                runtime_root=config.paths.runtime_root,
                requested_state=ControllerState.STOPPING,
            )
            should_exit = True

    service = ControllerService(
        SessionManager(session_factory),
        WorkerService(),
        launcher=launcher,
        sleep_fn=sleep_and_drive,
    )
    action = RunControllerAction(service)

    result = action(
        controller_id="default",
        config=config,
        workspace_root=tmp_path,
        use_workspace_instance=False,
    )

    assert result.item.state == ControllerState.STOPPED
    assert ControllerState.PAUSED in status_states
    assert ControllerState.ACTIVE in status_states
    assert len(launch_calls) == 1


def test_paused_controller_mode_does_not_refresh_worker_heartbeat(tmp_path: Path) -> None:
    database_path = tmp_path / "controller.db"
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session_manager = SessionManager(session_factory)
    seeded_at = datetime(2026, 3, 22, 23, 30, tzinfo=UTC)
    stale_heartbeat = seeded_at - timedelta(minutes=5)

    with session_manager.transaction() as session:
        session.add(
            WorkerModel(
                id="controller-default-agents-0",
                state="active",
                queues=["agent"],
                heartbeat_at=stale_heartbeat,
                started_at=seeded_at - timedelta(minutes=10),
            )
        )

    launch_calls: list[list[str]] = []
    should_exit = False

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self.pid = pid

        def poll(self) -> int | None:
            return 0 if should_exit else None

    def launcher(command: list[str], *, cwd: Path, stdout_path: Path, stderr_path: Path):
        launch_calls.append(command)
        return FakeProcess(1000 + len(launch_calls))

    config = EffectiveConfig(
        paths=RuntimePaths(
            config_file=tmp_path / "config.yaml",
            state_root=tmp_path / "state",
            runtime_root=tmp_path / "run",
            log_root=tmp_path / "logs",
            database_path=database_path,
        ),
        queue=QueueConfig(),
        worker=WorkerDefaults(),
        controller=ControllerConfig(
            pools={
                "agents": ControllerPoolConfig(
                    queues=["agent"],
                    concurrency=1,
                    restart_policy=RestartPolicy.ON_FAILURE,
                )
            }
        ),
    )

    sleep_calls = 0

    def sleep_and_drive(_: float) -> None:
        nonlocal sleep_calls, should_exit
        sleep_calls += 1
        if sleep_calls == 1:
            service.request_state(
                controller_id="default",
                runtime_root=config.paths.runtime_root,
                requested_state=ControllerState.PAUSED,
            )
            should_exit = True
        elif sleep_calls == 2:
            service.request_state(
                controller_id="default",
                runtime_root=config.paths.runtime_root,
                requested_state=ControllerState.STOPPING,
            )

    service = ControllerService(
        session_manager,
        WorkerService(),
        launcher=launcher,
        sleep_fn=sleep_and_drive,
        clock=lambda: seeded_at,
    )
    action = RunControllerAction(service)

    result = action(
        controller_id="default",
        config=config,
        workspace_root=tmp_path,
        use_workspace_instance=False,
    )

    assert result.item.state == ControllerState.STOPPED

    with session_manager.session() as session:
        worker = session.get(WorkerModel, "controller-default-agents-0")

    assert worker is not None
    assert ensure_utc(worker.heartbeat_at) == stale_heartbeat
    assert worker.state == "stopped"
