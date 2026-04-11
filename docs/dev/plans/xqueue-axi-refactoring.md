# xqueue AXI Refactoring Plan

## Status

- Date: 2026-04-10
- Status: Draft

## Goal

Refactor `xqueue` so the CLI is AXI-compliant while preserving the project's
existing strengths: Typer commands, typed response envelopes, stable JSON
shapes, and an untouched action layer.

The target end state is:

- `--output` / `-o` with `toon`, `json`, `jsonl`, and `text`
- an `Output` object as the single CLI rendering surface
- command contracts derived from existing response models
- field filtering via `--fields` and truncation control via `--full`
- structured errors on stdout across all formats
- a content-first bare `xq` home view
- Claude Code and Codex session hooks

## Why xqueue Is a Good AXI Candidate

xqueue is already closer to AXI than xcron was before its migration and closer
to xfind was before its first pass:

- it already has typed response envelopes in `libs/domain/responses.py`
- it already routes CLI execution through `apps/cli/runtime.py`
- it already centralizes output selection in `apps/cli/output.py`
- commands already return Pydantic domain/view models rather than raw dicts

That means the refactor can stay almost entirely at the CLI/presentation edge.
The design should lean into that advantage instead of rebuilding response or
action semantics from scratch.

## Reference Inputs

- `docs/dev/output.md`
- `/Users/ddebowczyk/.agents/skills/axi/SKILL.md`
- `/Users/ddebowczyk/projects/xfind/docs/dev/plans/xfind-axi-refactoring.md`
- `/Users/ddebowczyk/projects/xfind/research/axi-retrospective/xfind-axi-retrospective-2026-04-10.md`
- `apps/cli/output.py`
- `apps/cli/runtime.py`
- `apps/cli/main.py`
- `apps/cli/commands/*.py`
- `libs/domain/responses.py`
- `libs/domain/models.py`
- `pyproject.toml`

## Current Baseline

### What xqueue already has

- Typer CLI with a clear top-level command tree in `apps/cli/main.py`
- 30 operator-facing command entrypoints plus the bare `xq` root
- stable JSON response envelopes:
  - `ListResponse[T]`
  - `DetailResponse[T]`
  - `MutationResponse[T]`
  - `ErrorResponse`
- centralized command execution in `run_action()`
- centralized format selection in `OutputFormat`
- Rich isolated to the text path
- typed domain/view models for jobs, queues, workers, health, doctor, DB, and
  controller operations

### What xqueue is missing

- TOON output and a TOON adapter
- JSONL output
- `-o` short flag
- `--fields` and `--full`
- contract registry for field filtering and AXI defaults
- an `Output` object that owns rendering, validation, and errors
- a content-first home view
- session hook install/status/start/end flows
- contextual hints in output payloads

### Current architecture

Today the CLI path is:

1. command function builds services and action
2. command passes `output_format` to `run_action()`
3. `run_action()` executes the action
4. `emit_result()` or `emit_error()` serializes with either:
   - `json.dumps(...)`
   - `rich.pretty.Pretty(...)`

This is workable, but it forces the command surface to thread output plumbing
manually and leaves no natural place for contracts, field filtering, TOON
rendering, truncation, or contextual disclosure.

## Design Principles

### 1. Preserve the action layer

Do not refactor `libs/actions/*` for framework reasons. AXI work belongs at the
CLI/presentation boundary.

### 2. Keep JSON contracts stable

Existing JSON envelope shapes are a strength. AXI should extend them, not
discard them. Specifically:

- list commands keep `{ "items": [...] }`
- detail commands keep `{ "item": { ... } }`
- mutation commands keep `{ "ok": true, "item": { ... } }`
- errors keep `{ "ok": false, "error": { ... } }`

### 3. Add TOON at the boundary only

Only one small adapter should import the TOON dependency. Everything else
should work with Pydantic models and payload dictionaries.

### 4. Derive contracts from response models

xqueue already has response envelopes. Contracts should be derived from those
models and the underlying row/detail models instead of maintaining separate
hand-written field lists that can silently drift.

### 5. Migrate incrementally with tests green throughout

Default output should switch last, not first. The migration should preserve
current text/json behavior until the new pipeline is verified.

## Command Taxonomy

The command registry should include the bare root plus every current
operator-facing command. "Default fields" below are the target AXI defaults for
TOON and filtered JSON, not necessarily the full response shape.

| Command | Kind | Current Response Shape | Target Default Fields |
|---|---|---|---|
| `xq` | home | none yet; currently help text | `bin`, `description`, `queues`, `jobs`, `workers`, `help` |
| `enqueue` | mutation | `MutationResponse[JobDetail]` | `ok`, `item.id`, `item.queue`, `item.state`, `item.available_at` |
| `health` | diagnostics | `DetailResponse[HealthReport]` | `item.status`, `item.database_status`, `item.paused_queues`, `item.stale_leases`, `item.stale_workers` |
| `doctor` | diagnostics | `DetailResponse[DoctorReport]` | `item.status`, `item.checks` |
| `config show` | detail | `DetailResponse[...]` | `item` |
| `controller run` | mutation | `MutationResponse[ControllerStatusView]` or equivalent | `ok`, `item.controller_id`, `item.state`, `item.process_id`, `item.pools` |
| `controller status` | detail | `DetailResponse[ControllerStatusView]` or `DetailResponse[ManagedControllerStatusView]` | `item.controller_id`, `item.state`, `item.process_id`, `item.updated_at`, `item.pools` |
| `controller install` | mutation | `MutationResponse[ManagedControllerInstallView]` | `ok`, `item.manager`, `item.controller_id`, `item.service_name`, `item.action` |
| `controller uninstall` | mutation | `MutationResponse[ManagedControllerInstallView]` | `ok`, `item.manager`, `item.controller_id`, `item.service_name`, `item.action` |
| `controller start` | mutation | `MutationResponse[ManagedControllerInstallView]` or `MutationResponse[ControllerCommandResult]` | `ok`, `item.controller_id`, `item.action` or `item.requested_state` |
| `controller pause-intake` | mutation | `MutationResponse[ControllerCommandResult]` | `ok`, `item.controller_id`, `item.requested_state`, `item.control_path` |
| `controller resume-intake` | mutation | `MutationResponse[ControllerCommandResult]` | `ok`, `item.controller_id`, `item.requested_state`, `item.control_path` |
| `controller drain` | mutation | `MutationResponse[ControllerCommandResult]` | `ok`, `item.controller_id`, `item.requested_state`, `item.control_path` |
| `controller restart` | mutation | `MutationResponse[ControllerCommandResult]` | `ok`, `item.controller_id`, `item.requested_state`, `item.control_path` |
| `controller stop` | mutation | `MutationResponse[ControllerCommandResult]` | `ok`, `item.controller_id`, `item.requested_state`, `item.control_path` |
| `db check` | detail | `DetailResponse[DatabaseCheckResult]` | `item.status`, `item.database_path`, `item.integrity_result`, `item.missing_tables` |
| `db vacuum` | mutation | `MutationResponse[DatabaseVacuumResult]` | `ok`, `item.database_path`, `item.size_before_bytes`, `item.size_after_bytes` |
| `db reset-workspace-instance` | mutation | `MutationResponse[WorkspaceInstanceResetResult]` | `ok`, `item.state_root`, `item.removed_paths`, `item.recreated_paths` |
| `db cleanup-retention` | mutation | `MutationResponse[RetentionCleanupResult]` | `ok`, `item.cutoff_at`, `item.deleted_attempt_count`, `item.deleted_event_count`, `item.deleted_log_count` |
| `jobs list` | list | `ListResponse[JobSummary]` | `items.id`, `items.queue`, `items.state`, `items.available_at` |
| `jobs show` | detail | `DetailResponse[JobDetail]` | `item.id`, `item.queue`, `item.state`, `item.command`, `item.attempts`, `item.events` |
| `jobs cancel` | mutation | `MutationResponse[JobDetail]` or similar | `ok`, `item.id`, `item.state`, `item.worker_id` |
| `jobs retry` | mutation | `MutationResponse[JobDetail]` or similar | `ok`, `item.id`, `item.state`, `item.available_at` |
| `jobs delete` | mutation | `MutationResponse[DeleteJobResult]` | `ok`, `item.job_id`, `item.deleted_state`, `item.deleted_attempt_count`, `item.deleted_event_count` |
| `jobs tail` | detail | `DetailResponse[JobLogTailView]` | `item.job_id`, `item.attempt_number`, `item.stream`, `item.path`, `item.lines`, `item.truncated` |
| `jobs purge` | mutation | `MutationResponse[PurgeJobsResult]` | `ok`, `item.queue`, `item.deleted_count` |
| `queues list` | list | `ListResponse[QueueView]` | `items.name`, `items.state`, `items.paused_at` |
| `queues stats` | list | `ListResponse[QueueStatsView]` | `items.name`, `items.state`, `items.total_jobs`, `items.running_jobs`, `items.queued_jobs` |
| `queues pause` | mutation | `MutationResponse[QueueView]` | `ok`, `item.name`, `item.state`, `item.paused_at` |
| `queues resume` | mutation | `MutationResponse[QueueView]` | `ok`, `item.name`, `item.state` |
| `recover stale-leases` | mutation | `MutationResponse[RecoverStaleLeasesResult]` or detail-like envelope | `ok`, `item.recovered_count`, `item.items` |
| `worker` (bare) | mutation | same as `worker run` today | `ok`, `item.worker.id`, `item.worker.state`, `item.claimed_job` |
| `worker run` | mutation | `MutationResponse[WorkerPollResult]` | `ok`, `item.worker.id`, `item.worker.state`, `item.claimed_job` |
| `workers list` | list | `ListResponse[WorkerView]` | `items.id`, `items.state`, `items.queues`, `items.heartbeat_at` |
| `workers pause` | mutation | `MutationResponse[WorkerView]` | `ok`, `item.id`, `item.state`, `item.queues` |
| `workers resume` | mutation | `MutationResponse[WorkerView]` | `ok`, `item.id`, `item.state`, `item.queues` |
| `workers drain` | mutation | `MutationResponse[WorkerView]` | `ok`, `item.id`, `item.state`, `item.queues` |
| `workers stop` | mutation | `MutationResponse[WorkerView]` | `ok`, `item.id`, `item.state`, `item.queues` |

### Notes on taxonomy

- `config show` remains effectively unfiltered in text mode, but still gets a
  contract so JSON/TOON behavior stays explicit.
- `jobs show`, `jobs tail`, `health`, and `doctor` need truncation support for
  potentially large fields or lists.
- `worker` bare and `worker run` should share a single contract and response
  mapper because they are the same operation exposed through two entrypoints.
- `controller status` needs either:
  - one contract that covers both direct and managed views, or
  - two internal response models under one command contract

## Current vs Target Architecture

### Current

```text
Typer command
  -> action()
  -> run_action(fn, output_format=...)
     -> emit_result()/emit_error()
        -> json.dumps(...) or Rich Pretty(...)
```

Characteristics:

- simple and centralized
- no contracts
- no field filtering
- no TOON
- no JSONL
- no content-first home
- no session hooks

### Target

```text
Typer command
  -> out = Output(ctx, "command.name", local_output)
  -> response = action() or mapper(action())
  -> out.print(response)
     -> response.to_payload()
     -> contract-aware field filtering/truncation
     -> format dispatch:
        - toon  -> toon adapter
        - json  -> json.dumps
        - jsonl -> response.jsonl_items()
        - text  -> existing text renderers / Rich
```

Error path:

```text
Typer command / runtime
  -> out.error(...)
     -> ErrorResponse(...)
     -> same format dispatch on stdout
     -> typer.Exit(mapped_exit_code)
```

Key change: rendering responsibility moves from standalone helper functions to a
pre-configured `Output` instance scoped to one command invocation.

## Response Model Strategy

### Keep the existing envelopes

Unlike xfind's first pass, xqueue should not introduce new generic wrappers. It
already has the correct outer contracts.

Recommended base shape:

```python
class PayloadConvertible(BaseModel):
    def to_payload(self) -> dict[str, Any]: ...
    def jsonl_items(self) -> list[BaseModel] | None: ...
```

Then extend the current response models:

- `ListResponse[T]` inherits from `PayloadConvertible`
- `DetailResponse[T]` inherits from `PayloadConvertible`
- `MutationResponse[T]` inherits from `PayloadConvertible`
- `ErrorResponse` inherits from `PayloadConvertible`

Recommended behavior:

- `to_payload()` uses `model_dump(mode="json", exclude_none=True)`
- `ListResponse.jsonl_items()` returns `items`
- other response types return `None`

This preserves stable JSON while giving the `Output` pipeline one common
protocol.

### Typed rows and detail models stay in `libs/domain/models.py`

There is no need to duplicate `JobSummary`, `JobDetail`, `QueueView`,
`WorkerView`, `HealthReport`, and other domain-facing view models merely for
AXI. Contracts should reference them rather than cloning them into a second
module.

## Contract Strategy

Create a contract registry that uses the response model and, where needed, the
inner row/detail model to derive valid fields.

Suggested dataclass:

```python
@dataclass(frozen=True)
class CommandContract:
    name: str
    kind: CommandKind
    response_model: type[PayloadConvertible]
    item_model: type[BaseModel] | None = None
    default_fields: tuple[str, ...] = ()
    default_item_fields: tuple[str, ...] = ()
    truncation_limit: int | None = None
    hints: tuple[str, ...] = ()
```

Recommended derivation rules:

- top-level allowed fields come from `response_model.model_fields`
- row/detail fields come from `item_model.model_fields` when present
- validation fails at import time if defaults reference missing fields
- nested fields are opt-in and added only where xqueue needs them

This allows task `xqueue-yhg.3` to stay genuinely contract-first instead of
becoming a hand-maintained lookup table disconnected from response shapes.

## How `run_action()` Should Evolve

### Recommendation

Keep `run_action()` as the central error/exit-code wrapper, but change its
signature to accept an `Output` object instead of a bare `OutputFormat`.

Current:

```python
run_action(fn, output_format=output)
```

Target:

```python
out = Output(ctx, "jobs.list", output)
run_action(fn, out=out)
```

Target runtime behavior:

```python
def run_action(fn: Callable[[], PayloadConvertible], *, out: Output) -> None:
    try:
        out.print(fn())
    except XqueueError as exc:
        out.error(
            exc.message,
            code=exc.code,
            details=[...],
            exit_code=int(map_error_to_exit_code(exc)),
        )
```

### Why this is the right boundary

- commands stay minimal
- exit-code mapping remains centralized
- structured errors stay consistent
- the action layer remains untouched
- task `xqueue-yhg.4` becomes a mostly mechanical migration of call sites

## Home View Strategy

Bare `xq` should stop emitting Typer help by default. Instead it should render a
compact live dashboard oriented around the current workspace.

Suggested `HomeResponse`:

```python
class HomeResponse(PayloadConvertible):
    bin: str
    description: str
    queues: list[QueueHomeRow]
    jobs: list[JobHomeRow]
    workers: list[WorkerHomeRow]
    help: list[str]
```

Default home content should stay compact:

- a small queue summary
- a few recent or actionable jobs
- current worker/controller state
- 2-4 contextual next-step commands

The home command should be implemented via a top-level callback that renders
content when no subcommand was invoked instead of using `no_args_is_help=True`.

## Session Hook Strategy

Add explicit hooks commands and auto-install/self-heal behavior after the output
pipeline is in place.

Suggested command surface:

- `xq hooks install`
- `xq hooks status`
- `xq hooks session-start` (hidden)
- `xq hooks session-end` (hidden)

Responsibilities:

- install/update Claude Code and Codex hook definitions idempotently
- store absolute executable paths
- repair hook paths on subsequent invocations
- render a compact home-like snapshot on session start
- optionally capture session metadata on session end

Implementation should follow the xfind/xcron pattern but only after the home
view and `Output` path are stable.

## New File Map

### Files to create

```text
apps/cli/home.py                    # content-first top-level home response builder
apps/cli/hooks.py                   # shared hook lifecycle helpers
libs/domain/home.py                 # HomeResponse and small home row models
libs/domain/contracts.py            # CommandContract, CommandKind, registry helpers
libs/services/toon.py               # single TOON adapter wrapping python-toon
libs/services/session_hooks.py      # Claude Code / Codex hook installer/status logic
tests/cli/unit/test_output_axi.py   # Output unit tests
tests/cli/unit/test_contracts.py    # contract derivation tests
tests/cli/unit/test_toon.py         # TOON adapter tests
tests/cli/unit/test_home_view.py    # content-first xq root tests
tests/cli/unit/test_hooks_commands.py
tests/services/unit/test_session_hooks.py
tests/cli/regression/test_toon_output_contract.py
```

### Files to modify

```text
pyproject.toml                      # add python-toon dependency
apps/cli/output.py                  # OutputFormat enum, TOON support, Output class
apps/cli/runtime.py                 # run_action(fn, out=...)
apps/cli/main.py                    # global AXI options, home view, hooks wiring
apps/cli/commands/config.py         # switch to Output object
apps/cli/commands/controller.py     # switch to Output object
apps/cli/commands/db.py             # switch to Output object
apps/cli/commands/doctor.py         # switch to Output object
apps/cli/commands/enqueue.py        # switch to Output object
apps/cli/commands/health.py         # switch to Output object
apps/cli/commands/jobs.py           # switch to Output object
apps/cli/commands/queues.py         # switch to Output object
apps/cli/commands/recover.py        # switch to Output object
apps/cli/commands/worker.py         # switch to Output object
apps/cli/commands/workers.py        # switch to Output object
libs/domain/responses.py            # PayloadConvertible + jsonl_items support
```

### Files likely not to change

```text
libs/actions/*
libs/services/jobs.py
libs/services/queues.py
libs/services/workers.py
libs/services/controller.py
libs/infra/*
```

The only exceptions should be narrow behavior fixes discovered during
verification, not framework-driven rewrites.

## Phased Migration

### Phase 1: Plan and contract inventory

Scope:

- write this plan
- enumerate every command and its response shape
- decide target default fields and truncation candidates

Verification:

- plan is coherent
- no code changes yet

### Phase 2: Foundation primitives

Scope:

- add `python-toon` dependency
- add TOON adapter in one file
- extend `OutputFormat` to `toon|json|jsonl|text`
- add `PayloadConvertible` behavior to response envelopes
- introduce command contract types/registry
- introduce `Output` class in `apps/cli/output.py`

Guardrails:

- existing CLI commands still default to `text`
- current tests remain green

Verification:

- isolated tests for TOON adapter, contracts, and `Output.render()`

### Phase 3: Contract-derived command plumbing

Scope:

- make commands construct `Output(ctx, "<command>", output)`
- change `run_action()` to accept `out`
- add `--output/-o`, `--fields`, and `--full` global/shared options
- validate requested fields against the contract registry

Guardrails:

- default format stays `text` until migration is complete
- JSON shape remains unchanged for existing regression tests

Verification:

- command unit tests pass under `text` and `json`
- new tests cover field validation and JSONL selection

### Phase 4: Full call-site migration

Scope:

- replace all `run_action(..., output_format=output)` call sites
- remove direct `emit_result()` / `emit_error()` usage from command paths
- make error rendering flow through `out.error()`

Expected size:

- 43 call-site migrations across 11 command files

Guardrails:

- keep diffs mechanical and local
- do not combine migration with unrelated refactors

Verification:

- CLI unit tests pass
- no remaining `run_action(..., output_format=...)`
- no direct command-path calls to `emit_result()` / `emit_error()`

### Phase 5: Content-first home and hooks

Scope:

- make bare `xq` emit a compact live dashboard
- add hook install/status/session commands
- implement self-install/self-heal hook behavior

Guardrails:

- root command stays directory-scoped and compact
- hook definitions use absolute executable paths

Verification:

- `xq` with no args emits structured content, not help text
- hook install/status behavior is idempotent and tested

### Phase 6: Default output switch and cleanup

Scope:

- switch default output from `text` to `toon`
- keep `text`, `json`, and `jsonl` available
- remove obsolete helper plumbing
- normalize tests to assert stable structure instead of exact legacy shapes

Guardrails:

- `--output text` remains human-friendly
- `--output json` remains stable for automation

Verification:

- regression coverage for TOON, JSON, and JSONL
- no dead code from pre-AXI helpers

## Testing Strategy

### Unit tests

Add focused tests for:

- TOON adapter encoding of dict/object/list payloads
- contract derivation from response and item models
- `Output.render()` and `Output.print()` behavior per format
- `Output.error()` structured payloads and exit behavior
- field filtering and invalid field selection
- truncation and `--full`
- hook installer idempotency and path repair

### Command-level tests

Expand CLI tests to cover:

- `-o toon`, `-o json`, `-o jsonl`, `-o text`
- `--fields`
- `--full`
- root `xq` home output
- hidden hook command behavior where relevant

### Regression tests

Keep and extend coverage for:

- stable JSON envelopes
- exit-code behavior
- controller/worker flows
- existing operator command semantics

Prefer asserting structural guarantees instead of exact whole-payload key sets
when AXI adds stable metadata like `help`.

### Quality lane

Before closing later implementation tasks, run at minimum:

- `uv run pytest`
- `xqa profile run default`

If the Semgrep-backed lane is noisy or slow, still run:

- `xqa profile run style`

## Risks and Mitigations

### Risk: contract drift from real response shapes

Mitigation:

- derive allowed fields from Pydantic models
- add import-time validation tests

### Risk: changing JSON breaks existing automation

Mitigation:

- preserve response envelopes exactly
- keep JSON regression coverage
- switch default to TOON only after JSON parity is verified

### Risk: Typer global option propagation becomes noisy

Mitigation:

- centralize output option resolution in one helper or in `Output`
- do not invent a second command framework

### Risk: home view becomes too verbose

Mitigation:

- keep the dashboard compact and token-budget-aware
- put deeper state behind explicit commands

### Risk: hooks add platform-specific fragility

Mitigation:

- test installer logic against temp directories
- treat hooks as infrastructure with status inspection and repair

## Task Mapping

| Task | Planned scope |
|---|---|
| `xqueue-yhg.1` | produce and review this plan |
| `xqueue-yhg.2` | add TOON adapter, expanded `OutputFormat`, `Output` class |
| `xqueue-yhg.3` | add contract registry derived from response models |
| `xqueue-yhg.4` | migrate all command call sites from `run_action(..., output_format=...)` to `Output` |
| `xqueue-yhg.5` | add content-first home view and session hooks |
| `xqueue-yhg.6` | remove obsolete plumbing, harden tests, run verification |

## Review Gate

This plan is detailed enough to implement against directly. The one explicit
review point before deeper code changes is confirming the intended shape:

- preserve existing response envelopes
- evolve `run_action()` instead of deleting it
- keep the action layer untouched
- switch default output to TOON only near the end
- add home view and hooks after the output pipeline is stable

Unless new requirements emerge, the implementation tasks should follow this
sequence exactly.
