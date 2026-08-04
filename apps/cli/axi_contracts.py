"""CLI AXI contracts derived from structured request and response models."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel
from xqueue.controller.models import (
    ControllerCommandResult,
    ControllerPoolConfigView,
    ControllerStatusView,
    ManagedControllerInstallView,
    ManagedControllerStatusView,
)
from xqueue.jobs.models import DeleteJobResult, JobDetail, JobLogTailView, JobPaneView, JobPruneResult, JobSummary
from xqueue.maintenance.models import (
    DatabaseCheckResult,
    DatabaseVacuumResult,
    DoctorReport,
    HealthReport,
    RecoverStaleLeasesResult,
    RetentionCleanupResult,
    RuntimeMetricsResetView,
    RuntimeMetricsView,
)
from xqueue.queues.models import PurgeJobsResult, QueueStatsView, QueueView
from xqueue.workers.models import WorkerPollResult, WorkerView
from xqueue.workspace.models import (
    EffectiveConfig,
    HookInstallItem,
    HookStatusItem,
    SessionCaptureItem,
    WorkspaceInitResult,
    WorkspaceInstanceResetResult,
)
from xqueue_cli.contracts import (
    DetailResponse,
    ErrorDetail,
    ErrorResponse,
    ListResponse,
    MutationResponse,
)
from xqueue_cli.controller_pools import ControllerPoolMutationView
from xqueue_cli.home import HomeResponse

ModelLike = type[BaseModel] | tuple[type[BaseModel], ...]


@dataclass(frozen=True)
class CommandContract:
    """Declarative output contract for one CLI command."""

    name: str
    kind: str
    default_fields: tuple[str, ...]
    allowed_fields: tuple[str, ...]
    list_key: str | None = None
    list_row_fields: tuple[str, ...] = ()
    default_row_fields: tuple[str, ...] = ()
    item_key: str | None = None
    item_fields: tuple[str, ...] = ()
    default_item_fields: tuple[str, ...] = ()


def _field_names(model_class: ModelLike | None) -> tuple[str, ...]:
    if model_class is None:
        return ()
    models = model_class if isinstance(model_class, tuple) else (model_class,)
    fields: dict[str, None] = {}
    for model in models:
        for name in model.model_fields:
            fields.setdefault(name, None)
    return tuple(fields)


def contract_from_model(
    name: str,
    kind: str,
    model_class: type[BaseModel],
    *,
    default_fields: tuple[str, ...],
    list_key: str | None = None,
    list_row_model: ModelLike | None = None,
    default_row_fields: tuple[str, ...] = (),
    item_key: str | None = None,
    item_model: ModelLike | None = None,
    default_item_fields: tuple[str, ...] = (),
) -> CommandContract:
    """Derive a contract from a response model and optional nested models."""
    allowed_fields = tuple(model_class.model_fields.keys())
    list_row_fields = _field_names(list_row_model)
    item_fields = _field_names(item_model)

    missing_default_fields = set(default_fields) - set(allowed_fields)
    if missing_default_fields:
        raise ValueError(
            f"contract {name!r}: default_fields {sorted(missing_default_fields)} not present in {model_class.__name__}"
        )
    if list_key is not None and list_key not in allowed_fields:
        raise ValueError(f"contract {name!r}: list_key {list_key!r} not present in {model_class.__name__}")
    if item_key is not None and item_key not in allowed_fields:
        raise ValueError(f"contract {name!r}: item_key {item_key!r} not present in {model_class.__name__}")

    missing_row_defaults = set(default_row_fields) - set(list_row_fields)
    if missing_row_defaults:
        raise ValueError(
            f"contract {name!r}: default_row_fields {sorted(missing_row_defaults)} not present in row model fields"
        )

    missing_item_defaults = set(default_item_fields) - set(item_fields)
    if missing_item_defaults:
        raise ValueError(
            f"contract {name!r}: default_item_fields {sorted(missing_item_defaults)} not present in item model fields"
        )

    return CommandContract(
        name=name,
        kind=kind,
        default_fields=default_fields,
        allowed_fields=allowed_fields,
        list_key=list_key,
        list_row_fields=list_row_fields,
        default_row_fields=default_row_fields,
        item_key=item_key,
        item_fields=item_fields,
        default_item_fields=default_item_fields,
    )


def _build_contracts() -> dict[str, CommandContract]:
    controller_status_item = (ControllerStatusView, ManagedControllerStatusView)

    contracts = {
        "home": contract_from_model(
            "home",
            "home",
            HomeResponse,
            default_fields=("bin", "description", "queues", "jobs", "workers", "help"),
        ),
        "enqueue": contract_from_model(
            "enqueue",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=JobDetail,
            default_item_fields=("id", "queue", "state", "available_at"),
        ),
        "health": contract_from_model(
            "health",
            "diagnostics",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=HealthReport,
            default_item_fields=("status", "database_status", "paused_queues", "stale_leases", "stale_workers"),
        ),
        "doctor": contract_from_model(
            "doctor",
            "diagnostics",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=DoctorReport,
            default_item_fields=("status", "checks"),
        ),
        "config.show": contract_from_model(
            "config.show",
            "detail",
            EffectiveConfig,
            default_fields=("paths", "queue", "worker", "controller"),
        ),
        "controller.run": contract_from_model(
            "controller.run",
            "detail",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=ControllerStatusView,
            default_item_fields=("controller_id", "state", "process_id", "updated_at", "pools"),
        ),
        "controller.status": contract_from_model(
            "controller.status",
            "detail",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=controller_status_item,
            default_item_fields=("controller_id", "service_name"),
        ),
        "controller.pools.list": contract_from_model(
            "controller.pools.list",
            "list",
            ListResponse,
            default_fields=("items",),
            list_key="items",
            list_row_model=ControllerPoolConfigView,
            default_row_fields=("name", "queues", "concurrency"),
        ),
        "controller.pools.ensure": contract_from_model(
            "controller.pools.ensure",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=ControllerPoolMutationView,
            default_item_fields=("action", "name", "restart_required", "restart_command"),
        ),
        "controller.pools.remove": contract_from_model(
            "controller.pools.remove",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=ControllerPoolMutationView,
            default_item_fields=("action", "name", "restart_required", "restart_command"),
        ),
        "controller.install": contract_from_model(
            "controller.install",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=ManagedControllerInstallView,
            default_item_fields=("manager", "controller_id", "service_name", "action"),
        ),
        "controller.uninstall": contract_from_model(
            "controller.uninstall",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=ManagedControllerInstallView,
            default_item_fields=("manager", "controller_id", "service_name", "action"),
        ),
        "controller.start": contract_from_model(
            "controller.start",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=(ManagedControllerInstallView, ControllerCommandResult),
            default_item_fields=("controller_id", "action"),
        ),
        "controller.pause-intake": contract_from_model(
            "controller.pause-intake",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=ControllerCommandResult,
            default_item_fields=("controller_id", "requested_state", "control_path"),
        ),
        "controller.resume-intake": contract_from_model(
            "controller.resume-intake",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=ControllerCommandResult,
            default_item_fields=("controller_id", "requested_state", "control_path"),
        ),
        "controller.drain": contract_from_model(
            "controller.drain",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=ControllerCommandResult,
            default_item_fields=("controller_id", "requested_state", "control_path"),
        ),
        "controller.restart": contract_from_model(
            "controller.restart",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=(ManagedControllerInstallView, ControllerCommandResult),
            default_item_fields=("controller_id", "action"),
        ),
        "controller.stop": contract_from_model(
            "controller.stop",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=(ManagedControllerInstallView, ControllerCommandResult),
            default_item_fields=("controller_id", "action"),
        ),
        "db.check": contract_from_model(
            "db.check",
            "detail",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=DatabaseCheckResult,
            default_item_fields=("status", "database_path", "integrity_result", "missing_tables"),
        ),
        "db.vacuum": contract_from_model(
            "db.vacuum",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=DatabaseVacuumResult,
            default_item_fields=("database_path", "size_before_bytes", "size_after_bytes"),
        ),
        "workspace.init": contract_from_model(
            "workspace.init",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=WorkspaceInitResult,
            default_item_fields=("directory", "scope", "created_paths"),
        ),
        "db.reset-workspace-instance": contract_from_model(
            "db.reset-workspace-instance",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=WorkspaceInstanceResetResult,
            default_item_fields=("state_root", "removed_paths", "recreated_paths"),
        ),
        "db.cleanup-retention": contract_from_model(
            "db.cleanup-retention",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=RetentionCleanupResult,
            default_item_fields=("cutoff_at", "deleted_attempt_count", "deleted_event_count", "deleted_log_count"),
        ),
        "jobs.list": contract_from_model(
            "jobs.list",
            "list",
            ListResponse,
            default_fields=("items",),
            list_key="items",
            list_row_model=JobSummary,
            default_row_fields=("id", "queue", "state", "available_at"),
        ),
        "jobs.show": contract_from_model(
            "jobs.show",
            "detail",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=JobDetail,
            default_item_fields=("id", "queue", "state", "command", "attempts", "events"),
        ),
        "jobs.pane": contract_from_model(
            "jobs.pane",
            "detail",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=JobPaneView,
            default_item_fields=(
                "id",
                "state",
                "queue",
                "worker_id",
                "attempt_number",
                "elapsed_seconds",
                "process_status",
                "output_status",
                "stdout",
                "stderr",
            ),
        ),
        "jobs.cancel": contract_from_model(
            "jobs.cancel",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=JobDetail,
            default_item_fields=("id", "state", "worker_id", "cancel_requested_at"),
        ),
        "jobs.retry": contract_from_model(
            "jobs.retry",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=JobDetail,
            default_item_fields=("id", "state", "available_at", "attempt_count"),
        ),
        "jobs.delete": contract_from_model(
            "jobs.delete",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=DeleteJobResult,
            default_item_fields=("job_id", "deleted_state", "deleted_attempt_count", "deleted_event_count"),
        ),
        "jobs.tail": contract_from_model(
            "jobs.tail",
            "detail",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=JobLogTailView,
            default_item_fields=("job_id", "attempt_number", "stream", "path", "lines", "truncated"),
        ),
        "jobs.purge": contract_from_model(
            "jobs.purge",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=PurgeJobsResult,
            default_item_fields=("queue", "deleted_count"),
        ),
        "jobs.prune": contract_from_model(
            "jobs.prune",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=JobPruneResult,
            default_item_fields=(
                "dry_run",
                "state_filter",
                "older_than",
                "matched_job_count",
                "deleted_job_count",
                "deleted_attempt_count",
                "deleted_event_count",
                "deleted_log_count",
            ),
        ),
        "metrics.show": contract_from_model(
            "metrics.show",
            "detail",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=RuntimeMetricsView,
            default_item_fields=("path", "updated_at", "counters"),
        ),
        "metrics.reset": contract_from_model(
            "metrics.reset",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=RuntimeMetricsResetView,
            default_item_fields=("path", "updated_at", "counters", "previous_counters"),
        ),
        "queues.list": contract_from_model(
            "queues.list",
            "list",
            ListResponse,
            default_fields=("items",),
            list_key="items",
            list_row_model=QueueView,
            default_row_fields=("name", "state", "paused_at"),
        ),
        "queues.stats": contract_from_model(
            "queues.stats",
            "list",
            ListResponse,
            default_fields=("items",),
            list_key="items",
            list_row_model=QueueStatsView,
            default_row_fields=("name", "state", "total_jobs", "running_jobs", "queued_jobs"),
        ),
        "queues.pause": contract_from_model(
            "queues.pause",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=QueueView,
            default_item_fields=("name", "state", "paused_at"),
        ),
        "queues.resume": contract_from_model(
            "queues.resume",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=QueueView,
            default_item_fields=("name", "state", "paused_at"),
        ),
        "recover.stale-leases": contract_from_model(
            "recover.stale-leases",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=RecoverStaleLeasesResult,
            default_item_fields=("recovered_count", "items"),
        ),
        "worker": contract_from_model(
            "worker",
            "detail",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=WorkerPollResult,
            default_item_fields=("worker", "claimed_job"),
        ),
        "worker.run": contract_from_model(
            "worker.run",
            "detail",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=WorkerPollResult,
            default_item_fields=("worker", "claimed_job"),
        ),
        "workers.list": contract_from_model(
            "workers.list",
            "list",
            ListResponse,
            default_fields=("items",),
            list_key="items",
            list_row_model=WorkerView,
            default_row_fields=("id", "state", "queues", "heartbeat_at"),
        ),
        "workers.pause": contract_from_model(
            "workers.pause",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=WorkerView,
            default_item_fields=("id", "state", "queues", "heartbeat_at"),
        ),
        "workers.resume": contract_from_model(
            "workers.resume",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=WorkerView,
            default_item_fields=("id", "state", "queues", "heartbeat_at"),
        ),
        "workers.drain": contract_from_model(
            "workers.drain",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=WorkerView,
            default_item_fields=("id", "state", "queues", "heartbeat_at"),
        ),
        "workers.stop": contract_from_model(
            "workers.stop",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=WorkerView,
            default_item_fields=("id", "state", "queues", "heartbeat_at"),
        ),
        "error": contract_from_model(
            "error",
            "detail",
            ErrorResponse,
            default_fields=("ok", "error"),
            item_key="error",
            item_model=ErrorDetail,
            default_item_fields=("code", "message", "details"),
        ),
        "hooks.install": contract_from_model(
            "hooks.install",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=HookInstallItem,
            default_item_fields=("executable_path", "changed_files"),
        ),
        "hooks.status": contract_from_model(
            "hooks.status",
            "detail",
            DetailResponse,
            default_fields=("item",),
            item_key="item",
            item_model=HookStatusItem,
            default_item_fields=("executable_path", "claude", "codex"),
        ),
        "hooks.session-end": contract_from_model(
            "hooks.session-end",
            "mutation",
            MutationResponse,
            default_fields=("ok", "item"),
            item_key="item",
            item_model=SessionCaptureItem,
            default_item_fields=("log_path",),
        ),
    }

    return contracts


COMMAND_CONTRACTS = _build_contracts()


def get_command_contract(name: str) -> CommandContract:
    """Return the contract for one command."""
    try:
        return COMMAND_CONTRACTS[name]
    except KeyError:
        valid = ", ".join(sorted(COMMAND_CONTRACTS))
        raise KeyError(f"unknown command contract: {name!r}; valid names: {valid}") from None


def parse_fields_csv(value: str | None) -> tuple[str, ...]:
    """Parse a comma-separated field list into a stable tuple."""
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def allowed_request_fields(contract: CommandContract) -> frozenset[str]:
    """Return the full set of valid requestable fields for a contract."""
    allowed = set(contract.allowed_fields)
    allowed.update(contract.list_row_fields)
    allowed.update(contract.item_fields)

    if contract.list_key is not None:
        allowed.add(contract.list_key)
        allowed.update(f"{contract.list_key}.{field}" for field in contract.list_row_fields)
    if contract.item_key is not None:
        allowed.add(contract.item_key)
        allowed.update(f"{contract.item_key}.{field}" for field in contract.item_fields)

    return frozenset(allowed)


def validate_requested_fields(contract: CommandContract, requested: tuple[str, ...]) -> tuple[str, ...]:
    """Validate field requests against a command contract."""
    if not requested:
        return ()
    valid = allowed_request_fields(contract)
    invalid = [field for field in requested if field not in valid]
    if invalid:
        raise ValueError(
            f"unknown fields for {contract.name}: {', '.join(invalid)}; valid fields: {', '.join(sorted(valid))}"
        )
    return requested


__all__ = [
    "COMMAND_CONTRACTS",
    "CommandContract",
    "allowed_request_fields",
    "contract_from_model",
    "get_command_contract",
    "parse_fields_csv",
    "validate_requested_fields",
]
