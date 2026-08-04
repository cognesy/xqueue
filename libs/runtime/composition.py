"""Single composition root for xqueue runtime resources."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from importlib.metadata import version
from pathlib import Path

from sqlalchemy import Engine
from xqueue.adapters.filesystem.metrics import MetricsService
from xqueue.adapters.sqlite.database import create_session_factory, create_sqlite_engine
from xqueue.adapters.sqlite.session import SessionManager
from xqueue.controller.actions import (
    EnsureControllerPoolAction,
    ListControllerPoolsAction,
    RemoveControllerPoolAction,
    RequestControllerStateAction,
    RunControllerAction,
    ShowControllerStatusAction,
)
from xqueue.controller.launchd import LaunchdService
from xqueue.controller.models import ServiceManagerKind
from xqueue.controller.pools import ControllerPoolConfigService
from xqueue.controller.ports import ManagedControllerPort
from xqueue.controller.supervisor import ControllerService
from xqueue.controller.systemd import SystemdUserService
from xqueue.core.errors import XqueueClosedError
from xqueue.jobs.actions import (
    CancelJobAction,
    DeleteJobAction,
    EnqueueJobAction,
    JobPaneAction,
    ListJobsAction,
    PruneJobsAction,
    RetryJobAction,
    ShowJobAction,
    TailJobLogsAction,
)
from xqueue.jobs.logs import JobLogService
from xqueue.jobs.pruning import JobPruningService
from xqueue.jobs.store import JobService
from xqueue.maintenance.actions import (
    CheckDatabaseAction,
    CleanupRetentionAction,
    DoctorAction,
    HealthAction,
    VacuumDatabaseAction,
)
from xqueue.maintenance.database import DatabaseMaintenanceService
from xqueue.maintenance.health import HealthService
from xqueue.maintenance.metrics_actions import ResetMetricsAction, ShowMetricsAction
from xqueue.maintenance.recovery import RecoveryService
from xqueue.maintenance.recovery_actions import RecoverStaleLeasesAction
from xqueue.maintenance.retention import RetentionCleanupService
from xqueue.queues.actions import (
    ListQueuesAction,
    ListQueueStatsAction,
    PauseQueueAction,
    PurgeJobsAction,
    ResumeQueueAction,
)
from xqueue.queues.store import QueueService
from xqueue.runtime.logging import LoggingConfig, configure_logging, load_logging_config
from xqueue.workers.attempts import AttemptService
from xqueue.workers.orchestration import (
    ClaimNextJobAction,
    ListWorkersAction,
    RegisterWorkerAction,
    RunningWorkerCommandsAction,
    RunWorkerAction,
    RunWorkerLoopAction,
    SetWorkerStateAction,
)
from xqueue.workers.process import CommandExecutionService
from xqueue.workers.store import WorkerService
from xqueue.workspace.actions import (
    InitializeWorkspaceAction,
    ResetWorkspaceInstanceAction,
    ShowConfigAction,
)
from xqueue.workspace.init import WorkspaceInitService
from xqueue.workspace.inputs import ConfigInputs
from xqueue.workspace.instance import WorkspaceInstanceService
from xqueue.workspace.loader import SettingsLoader
from xqueue.workspace.models import EffectiveConfig, WorkspaceInitResult
from xqueue.workspace.paths import Workspace, WorkspaceScope
from xqueue.workspace.resolver import project_workspace, resolve_workspace


@dataclass(frozen=True)
class JobActions:
    """Job use cases assembled once for one runtime."""

    enqueue: EnqueueJobAction
    list: ListJobsAction
    show: ShowJobAction
    pane: JobPaneAction
    cancel: CancelJobAction
    retry: RetryJobAction
    delete: DeleteJobAction
    tail: TailJobLogsAction
    prune: PruneJobsAction


@dataclass(frozen=True)
class QueueActions:
    """Queue use cases assembled once for one runtime."""

    list: ListQueuesAction
    stats: ListQueueStatsAction
    pause: PauseQueueAction
    resume: ResumeQueueAction
    purge: PurgeJobsAction


@dataclass(frozen=True)
class WorkerActions:
    """Worker registry and claim use cases assembled once for one runtime."""

    register: RegisterWorkerAction
    list: ListWorkersAction
    set_state: SetWorkerStateAction
    claim: ClaimNextJobAction
    running_commands: RunningWorkerCommandsAction


@dataclass(frozen=True)
class WorkerRunner:
    """One configured direct-worker poll and loop pair."""

    poll: RunWorkerAction
    loop: RunWorkerLoopAction


@dataclass(frozen=True)
class ControllerActions:
    """Direct controller and pool use cases assembled for one runtime."""

    run: RunControllerAction
    status: ShowControllerStatusAction
    request_state: RequestControllerStateAction
    list_pools: ListControllerPoolsAction
    ensure_pool: EnsureControllerPoolAction
    remove_pool: RemoveControllerPoolAction


@dataclass(frozen=True)
class MaintenanceActions:
    """Operational maintenance use cases assembled for one runtime."""

    health: HealthAction
    doctor: DoctorAction
    check_database: CheckDatabaseAction
    vacuum_database: VacuumDatabaseAction
    cleanup_retention: CleanupRetentionAction
    recover_stale_leases: RecoverStaleLeasesAction
    show_metrics: ShowMetricsAction
    reset_metrics: ResetMetricsAction


class PlatformKind(StrEnum):
    LAUNCHD = "launchd"
    SYSTEMD_USER = "systemd-user"
    DIRECT = "direct"


def detect_platform() -> PlatformKind:
    if sys.platform == "darwin":
        return PlatformKind.LAUNCHD
    if sys.platform.startswith("linux"):
        return PlatformKind.SYSTEMD_USER
    return PlatformKind.DIRECT


def resolve_open_workspace(
    *,
    workspace_root: Path | None,
    use_workspace_instance: bool,
) -> Workspace:
    """Turn the two open() arguments into one decided workspace.

    `use_workspace_instance` is the deprecated spelling of "the workspace at
    this root": it predates the marker and named the directory `instance/`.
    It now selects the same project workspace `--workspace` would.

    Otherwise the resolver runs its four steps, with the caller's root as the
    discovery start. Discovery never starts implicitly from the working
    directory -- the CLI supplies it, the SDK does not have to.
    """
    if use_workspace_instance:
        if workspace_root is None:
            raise ValueError("workspace_root is required when use_workspace_instance=True")
        return project_workspace(workspace_root)

    resolved = resolve_workspace(start_dir=workspace_root)
    if resolved.scope is WorkspaceScope.HOME:
        # State lives in the machine-wide instance, but agent hooks and other
        # repo-local artifacts still belong to the directory the caller named.
        return replace(resolved, root=(workspace_root or Path.cwd()).expanduser().resolve())
    return resolved


class Runtime:
    """Own resolved configuration, database resources, and shared services."""

    def __init__(
        self,
        *,
        config: EffectiveConfig,
        engine: Engine,
        session_manager: SessionManager,
        maintenance_actions: MaintenanceActions,
        reset_workspace_instance: ResetWorkspaceInstanceAction,
        job_actions: JobActions,
        queue_actions: QueueActions,
        worker_actions: WorkerActions,
        worker_service: WorkerService,
        job_service: JobService,
        controller_actions: ControllerActions,
        workspace: Workspace,
        initialize_workspace_action: InitializeWorkspaceAction,
        config_inputs: ConfigInputs,
        metrics: MetricsService,
        logging: LoggingConfig,
        platform: PlatformKind,
    ) -> None:
        self.config = config
        self.engine = engine
        self.session_manager = session_manager
        self.maintenance_actions = maintenance_actions
        self.reset_workspace_instance = reset_workspace_instance
        self.job_actions = job_actions
        self.queue_actions = queue_actions
        self.worker_actions = worker_actions
        self._worker_service = worker_service
        self._job_service = job_service
        self.controller_actions = controller_actions
        self.workspace = workspace
        self._initialize_workspace_action = initialize_workspace_action
        # Kept so `reload_config` composes from the same inputs the first load
        # used. Rereading only the workspace file would silently drop the
        # explicit file, the named env, and every --set the caller passed.
        self._config_inputs = config_inputs
        self.metrics = metrics
        self.logging = logging
        self.platform = platform
        self._closed = False

    @classmethod
    def open(
        cls,
        *,
        config_path: Path | None,
        workspace_root: Path | None,
        use_workspace_instance: bool,
        workspace: Workspace | None = None,
        env_name: str | None = None,
        overrides: Mapping[str, str] | None = None,
        configure_process_logging: bool = False,
    ) -> Runtime:
        # Opt-in: opening a runtime must not replace an embedding host's structlog
        # configuration. The CLI asks for it explicitly at process start.
        if configure_process_logging:
            configure_logging()
        resolved_workspace = workspace or resolve_open_workspace(
            workspace_root=workspace_root,
            use_workspace_instance=use_workspace_instance,
        )
        config_inputs = ConfigInputs(
            config_path=config_path,
            env_name=env_name,
            overrides=dict(overrides or {}),
        )
        config = ShowConfigAction(SettingsLoader())(resolved_workspace, inputs=config_inputs)
        engine = create_sqlite_engine(config.paths.database_path)
        session_manager = SessionManager(create_session_factory(engine))
        database_service = DatabaseMaintenanceService(engine, database_path=config.paths.database_path)
        health_service = HealthService()
        job_service = JobService()
        job_log_service = JobLogService()
        queue_service = QueueService()
        metrics = MetricsService(config.paths.state_root / "metrics" / "metrics.json")
        worker_service = WorkerService(job_service, queue_service)
        job_actions = JobActions(
            enqueue=EnqueueJobAction(session_manager, job_service, metrics=metrics),
            list=ListJobsAction(session_manager, job_service),
            show=ShowJobAction(session_manager, job_service),
            pane=JobPaneAction(session_manager, job_service),
            cancel=CancelJobAction(session_manager, job_service),
            retry=RetryJobAction(session_manager, job_service),
            delete=DeleteJobAction(session_manager, job_service, job_log_service),
            tail=TailJobLogsAction(session_manager, job_service, job_log_service),
            prune=PruneJobsAction(session_manager, JobPruningService(), job_log_service),
        )
        queue_actions = QueueActions(
            list=ListQueuesAction(session_manager, queue_service),
            stats=ListQueueStatsAction(session_manager, queue_service),
            pause=PauseQueueAction(session_manager, queue_service),
            resume=ResumeQueueAction(session_manager, queue_service),
            purge=PurgeJobsAction(session_manager, queue_service),
        )
        worker_actions = WorkerActions(
            register=RegisterWorkerAction(session_manager, worker_service),
            list=ListWorkersAction(session_manager, worker_service),
            set_state=SetWorkerStateAction(session_manager, worker_service),
            claim=ClaimNextJobAction(session_manager, worker_service),
            running_commands=RunningWorkerCommandsAction(session_manager, worker_service),
        )
        controller_service = ControllerService(session_manager, worker_service)
        pool_config = ControllerPoolConfigService()
        controller_actions = ControllerActions(
            run=RunControllerAction(controller_service),
            status=ShowControllerStatusAction(controller_service),
            request_state=RequestControllerStateAction(controller_service),
            list_pools=ListControllerPoolsAction(pool_config),
            ensure_pool=EnsureControllerPoolAction(pool_config),
            remove_pool=RemoveControllerPoolAction(pool_config),
        )
        maintenance_actions = MaintenanceActions(
            health=HealthAction(session_manager, health_service, database_service),
            doctor=DoctorAction(session_manager, health_service, database_service),
            check_database=CheckDatabaseAction(database_service),
            vacuum_database=VacuumDatabaseAction(database_service),
            cleanup_retention=CleanupRetentionAction(
                session_manager,
                RetentionCleanupService(),
                job_log_service,
            ),
            recover_stale_leases=RecoverStaleLeasesAction(
                session_manager,
                RecoveryService(),
                retry_delay_seconds=config.worker.retry_delay_seconds,
            ),
            show_metrics=ShowMetricsAction(metrics),
            reset_metrics=ResetMetricsAction(metrics),
        )
        return cls(
            config=config,
            engine=engine,
            session_manager=session_manager,
            maintenance_actions=maintenance_actions,
            reset_workspace_instance=ResetWorkspaceInstanceAction(WorkspaceInstanceService()),
            job_actions=job_actions,
            queue_actions=queue_actions,
            worker_actions=worker_actions,
            worker_service=worker_service,
            job_service=job_service,
            controller_actions=controller_actions,
            workspace=resolved_workspace,
            initialize_workspace_action=InitializeWorkspaceAction(WorkspaceInitService()),
            config_inputs=config_inputs,
            metrics=metrics,
            logging=load_logging_config(),
            platform=detect_platform(),
        )

    def ensure_open(self) -> None:
        if self._closed:
            raise XqueueClosedError("xqueue runtime is closed")

    def effective_config(self) -> EffectiveConfig:
        self.ensure_open()
        return self.config

    def build_worker_runner(
        self,
        *,
        default_timeout_seconds: int | None = None,
        cancel_grace_period_seconds: int | None = None,
        retry_delay_seconds: int | None = None,
    ) -> WorkerRunner:
        """Compose a direct worker with command-level setting overrides."""
        self.ensure_open()
        poll = RunWorkerAction(
            self.session_manager,
            self._worker_service,
            job_service=self._job_service,
            attempt_service=AttemptService(self._job_service),
            execution_service=CommandExecutionService(),
            log_root=self.config.paths.log_root,
            default_timeout_seconds=(
                self.config.worker.default_timeout_seconds
                if default_timeout_seconds is None
                else default_timeout_seconds
            ),
            cancel_grace_period_seconds=(
                self.config.worker.cancel_grace_period_seconds
                if cancel_grace_period_seconds is None
                else cancel_grace_period_seconds
            ),
            retry_delay_seconds=(
                self.config.worker.retry_delay_seconds if retry_delay_seconds is None else retry_delay_seconds
            ),
            metrics=self.metrics,
        )
        return WorkerRunner(poll=poll, loop=RunWorkerLoopAction(poll))

    def reload_config(self) -> EffectiveConfig:
        self.ensure_open()
        self.config = SettingsLoader().load(self.workspace, inputs=self._config_inputs)
        return self.config

    def initialize_workspace(self, *, force: bool = False) -> WorkspaceInitResult:
        self.ensure_open()
        return self._initialize_workspace_action(
            self.workspace,
            created_by=f"xqueue {version('xqueue')}",
            force=force,
        )

    @property
    def workspace_root(self) -> Path:
        """Where hooks and repo-local artifacts belong: the workspace's root."""
        return self.workspace.root

    @property
    def use_workspace_instance(self) -> bool:
        """Whether spawned children must be pinned to this project workspace.

        The controller launches workers and launchd/systemd units that open
        their own runtime, and they have to land on the workspace this one
        decided rather than resolving again from scratch. Both are started with
        the workspace root as their working directory, so `--workspace-instance`
        pins them exactly there.

        This is derived from the decided workspace rather than remembered from
        an argument, which closes a real gap: a client that *discovered* a
        project workspace used to spawn children that fell back to the home
        instance.
        """
        return self.workspace.scope is WorkspaceScope.PROJECT

    def managed_controller_service(self, platform: ServiceManagerKind | None = None) -> ManagedControllerPort:
        """Select the host adapter without leaking it into SDK or CLI code."""
        self.ensure_open()
        selected = platform
        if selected is None:
            if self.platform is PlatformKind.LAUNCHD:
                selected = ServiceManagerKind.LAUNCHD
            elif self.platform is PlatformKind.SYSTEMD_USER:
                selected = ServiceManagerKind.SYSTEMD
            else:
                from xqueue.core.errors import ValidationError

                raise ValidationError("no supported managed controller platform for this system")
        if selected is ServiceManagerKind.LAUNCHD:
            return LaunchdService(python_executable=sys.executable)
        if selected is ServiceManagerKind.SYSTEMD:
            return SystemdUserService(python_executable=sys.executable)
        from xqueue.core.errors import ValidationError

        raise ValidationError("unsupported managed controller platform", details={"platform": selected.value})

    def close(self) -> None:
        if self._closed:
            return
        self.engine.dispose()
        self._closed = True
