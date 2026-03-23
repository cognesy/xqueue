# xqueue Specification Implementation Plan

## Goal

Implement `xqueue` (`xq`) as a CLI-first, single-machine durable work queue for
shell commands, following `SPEC.md`, `AGENTS.md`, and the target repository
layout and layering rules:

- `apps/` contains runnable application shells only
- `libs/` contains importable shared code only
- `resources/` contains static project assets such as config and Alembic files
- `tests/<module>/{unit,feature,integration,regression}/` organizes coverage by
  module and test level
- `instance/` contains mutable local runtime state such as SQLite and logs
- `docs/{dev,spec,user}/` contains developer, spec, and user documentation

Application layering must remain strict:

- app shells call actions, not services
- actions are constructor-injected use cases
- services provide context-agnostic integration with libraries and system
  boundaries

## Current State

The repository currently contains only the specification and agent guidance:

- `SPEC.md`
- `AGENTS.md`
- split spec chapters under `docs/spec/`

There is no existing implementation, architecture document, project skeleton,
or backlog. That means the initial plan must cover both bootstrapping the code
structure and implementing the first useful milestone.

## Constraints

The plan must preserve the non-negotiable constraints from the specification:

- Python project managed with `uv`
- Typer CLI
- Rich only for text rendering
- stable `--output json` contracts that bypass Rich entirely
- SQLite as canonical mutable state store
- Alembic from day one
- SQLite in WAL mode with explicit transactions and sensible `busy_timeout`
- Pydantic models separate from SQLAlchemy ORM models
- stdout/stderr captured in files, not DB blobs
- `structlog` for application logs
- command-first job model
- process-group-based execution for timeout and cancellation correctness
- at-least-once execution semantics with stale lease recovery

## Implementation Strategy

Build `xqueue` in phases, starting with foundations that enforce repository
structure and architecture boundaries before layering in durable queue behavior,
worker execution, and later controller and platform integrations.

The first delivery tranche should harden the milestone explicitly called out in
`SPEC.md`:

1. enqueue command jobs into SQLite
2. run one worker process
3. support `queued`, `running`, `succeeded`, `failed`, `canceled`
4. support retries and timeouts
5. expose `jobs list/show/cancel/retry` via CLI
6. emit JSON for automation

After that baseline is solid, expand toward queue control, worker management,
recovery, health tooling, controller supervision, and platform service
integration.

## Proposed Architecture

### Repo layout

```text
apps/
  cli/
libs/
  actions/
  domain/
  infra/
  services/
resources/
  alembic/
  config/
  schemas/
tests/
  cli/
    unit/
    feature/
    integration/
    regression/
  actions/
    unit/
    feature/
    integration/
    regression/
  infra/
    unit/
    feature/
    integration/
    regression/
  services/
    unit/
    feature/
    integration/
    regression/
instance/
docs/
  dev/
  spec/
  user/
```

### Layering

- `apps/cli/` owns Typer command wiring, argument parsing, exit code mapping,
  and output selection.
- `libs/actions/` owns use cases such as enqueueing jobs, listing jobs,
  claiming work, recording heartbeats, canceling jobs, retrying jobs, and
  recovering stale leases.
- `libs/services/` owns infrastructure-facing adapters such as SQLite session
  management, repository/query services, subprocess/process-group execution,
  file-based log capture, config loading, clock/ID generation, and platform
  service management.
- `libs/domain/` owns Pydantic schemas, enums, response contracts, and domain
  rules that must stay separate from ORM concerns.
- `libs/infra/` owns SQLAlchemy models, database setup, Alembic integration,
  repository implementations, and low-level filesystem/runtime path helpers.

This preserves the dependency flow:

`apps -> actions -> services`

with domain and infra types supporting those layers without turning the app
shells into orchestration code.

## Phased Breakdown

### Phase 0: Bootstrap and architectural guardrails

Establish the project skeleton, dependency management, packaging, directory
layout, and shared conventions so later implementation lands in the right place
instead of being retrofitted.

### Phase 1: Durable data model and persistence foundation

Implement configuration, platform-aware paths, SQLite setup, WAL and transaction
behavior, SQLAlchemy models, domain schemas, and Alembic migrations.

### Phase 2: CLI contracts and operator-facing job APIs

Implement the initial CLI shell, output abstraction, JSON contracts, enqueue,
jobs list/show, and config inspection in a way that keeps text and JSON
completely separate.

### Phase 3: Worker execution core

Implement atomic claim logic, worker registration and heartbeat, subprocess
execution, stdout/stderr capture, timeout handling, retries, and terminal state
updates.

### Phase 4: Control-plane operations and recovery

Implement cancellation, retry, queue pause/resume/purge, worker state control,
stale lease recovery, health checks, doctor checks, and database maintenance
commands.

### Phase 5: Controller supervision and platform integration

Implement the long-running controller, static worker-pool config, restart
policy, and managed `launchd` / `systemd --user` artifact rendering with strict
ownership boundaries.

### Phase 6: Hardening, documentation, and regression coverage

Expand testing around concurrency, crash recovery, output stability, and
operator workflows; add developer and user documentation for installation,
runtime operation, and recovery procedures.

## Planned Backlog Structure

Create one top-level epic for the full specification and child epics for each
phase:

1. Foundation and project bootstrap
2. Persistence and schema foundation
3. CLI contracts and basic job operations
4. Worker runtime and attempt lifecycle
5. Queue, worker, and recovery operations
6. Controller and platform integration
7. Hardening, docs, and release readiness

Under those epics, create atomic tasks with explicit dependencies. Early tasks
should optimize for unblocking the first milestone before broader controller and
service-manager work.

## Initial Task Sequence

1. Bootstrap project structure, `uv` metadata, package entrypoints, and target
   directories.
2. Define architecture guidance and shared conventions for layering, output
   contracts, runtime paths, and instance data ownership.
3. Implement configuration loading and path resolution using `platformdirs`.
4. Implement SQLite engine/session setup with WAL, `busy_timeout`, and explicit
   transaction helpers.
5. Add SQLAlchemy persistence models and initial Alembic migration for `jobs`,
   `attempts`, `workers`, and optional `events`.
6. Add domain enums, Pydantic models, and JSON response schemas that remain
   separate from ORM models.
7. Build the CLI app shell and output abstraction for `text|json`.
8. Implement enqueue and jobs list/show actions plus CLI commands.
9. Implement worker registration, claim leasing, and one-process worker loop.
10. Implement subprocess execution with process groups and file-based
    stdout/stderr capture.
11. Implement timeout, retry scheduling, and attempt history updates.
12. Implement cancel and retry commands with distinct cancellation metadata.
13. Implement stale lease recovery, health, doctor, and DB maintenance
    commands.
14. Implement queue and worker control commands and their state transitions.
15. Implement controller process, config-driven pools, and direct supervision.
16. Implement platform service artifact rendering and lifecycle integration.
17. Add comprehensive test coverage and operator documentation.

## Risks

- atomic claim logic is easy to get subtly wrong under concurrency
- timeout and cancellation semantics depend on correct process-group handling
- JSON output stability can erode if text rendering concerns leak upward
- controller and platform integration can distort the local-first design if
  introduced too early
- repo structure and layer boundaries can drift unless enforced from the first
  tasks

## Trade-offs

- Prioritize correctness and inspectability over speed of adding surface area.
- Delay sophisticated controller/platform features until the worker and
  persistence core are proven.
- Keep shell-mode command execution primary in v1; avoid early investment in
  advanced exec-mode abstractions.
- Add `events` support in the initial schema if cheap, but avoid letting it
  block milestone work.

## Open Questions

- Whether to implement `events` in the first migration or stage it immediately
  after the core schema if needed to keep the first milestone tight.
- Whether queue pause state should live in a dedicated table from the start or
  be represented through queue metadata derived from jobs plus static config.
- Whether controller and worker runtime wrappers should be generated in
  `instance/` or a platformdirs-managed runtime directory outside the repo when
  running normally.
- Whether to add explicit `timed_out` as an attempt outcome only in v1 while
  keeping top-level job states limited to the required baseline.

## Research Notes

The plan aligns with current official guidance and project constraints:

- Typer supports multi-file command organization well, which fits thin app
  shells under `apps/cli/`.
- SQLAlchemy 2.x remains the appropriate persistence layer for explicit session
  and transaction control against SQLite.
- Alembic remains the right fit for schema evolution from the first migration.

These reinforce the spec decisions rather than changing them.

## Review Checklist

- [ ] Phase ordering keeps the first milestone on the critical path
- [ ] Tasks enforce the required app/action/service separation
- [ ] Persistence design keeps ORM models separate from domain schemas
- [ ] CLI design keeps `text` and `json` output paths separate
- [ ] Controller and platform work is sequenced after worker correctness
- [ ] Test tasks cover concurrency, cancellation, timeout, and stale-lease risk
