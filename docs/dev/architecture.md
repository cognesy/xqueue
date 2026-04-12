# Architecture

## Purpose

This document defines the repository layout, layer responsibilities, dependency
direction, and runtime data ownership for `xqueue`.

It is intentionally strict. The project is small enough that architectural
drift would be more damaging than a small amount of ceremony.

## Core Rule

`xqueue` is built around this dependency direction:

`apps -> actions -> services`

App shells may not call services directly.

## Repository Layout

### Runnable surfaces

`apps/` contains deployable or runnable entrypoints only.

Examples:

- CLI commands
- worker processes
- controller processes
- future API or web entrypoints, if they are ever added

These modules own shell concerns only:

- argument and option parsing
- process startup
- command registration
- mapping exceptions to exit codes
- selecting text versus JSON rendering

They must stay slim. They construct actions, invoke them, and translate results
to the surface being served.

### Shared libraries

`libs/` contains importable code only. Nothing in `libs/` is a deployment
surface by itself.

Current layer split:

- `libs/actions/`
- `libs/domain/`
- `libs/infra/`
- `libs/services/`

### Static project assets

`resources/` contains non-code project assets.

Examples:

- Alembic environment and migrations
- configuration templates
- schemas
- static sample data if needed later

Mutable queue state must never live here.

### Tests

Tests are organized by module and then by test level:

`tests/<module>/{unit,feature,integration,regression}/`

This keeps verification aligned with the code surface being exercised instead of
collapsing everything into one flat test tree.

### Local mutable runtime state

`instance/` is the repository-local area for development-time mutable state.

Examples:

- SQLite databases used for local runs
- local stdout/stderr capture during development
- local runtime files created for manual testing

In normal installed usage, runtime state resolves under `~/.xqueue/`. In-repo
`instance/` remains the local development analogue, not the canonical product
source tree.

### Documentation

Documentation is split by audience:

- `docs/dev/` for developer workflow and architecture
- `docs/spec/` for split specification chapters
- `docs/user/` for operator-facing usage documentation

## Layer Responsibilities

### Apps

`apps/` owns thin shells only.

Allowed responsibilities:

- parse CLI input with Typer
- instantiate actions with explicit dependencies
- invoke one or more actions in a simple shell flow
- construct the shared `Output` surface and pass the command contract name
- map domain or action exceptions to stable exit codes

Forbidden responsibilities:

- direct SQLAlchemy session usage
- direct subprocess execution
- filesystem or platform service orchestration
- embedding domain rules or state-transition logic
- calling services directly

Valid flow:

`CLI command -> action -> service`

Invalid flow:

`CLI command -> service`

### Actions

`libs/actions/` contains use cases.

Each action should be a small, explicit unit representing one capability such
as:

- enqueue a job
- list jobs
- show job details
- claim one runnable job
- record a worker heartbeat
- cancel a job
- recover stale leases

Actions receive dependencies through the constructor. They coordinate domain
rules, call services, and return domain-layer results.

Actions may:

- validate application-level invariants
- orchestrate multiple services
- define state-transition logic
- translate low-level failures into domain-meaningful errors

Actions may not:

- own CLI formatting
- own Rich rendering
- directly behave like infrastructure singletons hidden behind globals

### Services

`libs/services/` contains context-agnostic integrations with infrastructure and
system boundaries.

Examples:

- process execution and process-group control
- log file capture and path allocation
- configuration loading support
- clock and identifier providers
- platform service manager integrations
- repository/query interfaces implemented over infrastructure

Services are reusable across shells. They should not know whether they are
being called from a CLI command, worker process, or future API surface.

### Domain

`libs/domain/` contains domain-layer types and contracts.

Examples:

- enums for job state and worker state
- Pydantic models for job, attempt, and worker views
- request and response envelopes
- structured error schemas

Domain models are not ORM models.

### Infrastructure

`libs/infra/` contains low-level implementation details for persistence and
runtime support.

Examples:

- SQLAlchemy ORM models
- SQLite engine and session setup
- Alembic wiring
- repository implementations
- low-level path helpers tied to concrete storage details

Infrastructure should not leak into app shells.

## Output Boundaries

Structured output paths must remain separate from human-readable rendering.

Rules:

- Rich is only for human-readable text output
- `json`, `jsonl`, and `toon` must bypass Rich entirely
- JSON responses should be built from domain-layer models, not presentation
  models
- presentation-only fields must not leak into JSON output

Practical implication:

- app shells choose the command contract and local output override
- actions return domain results
- the `Output` object owns TOON/JSON/JSONL/text dispatch
- JSON serialization uses stable domain contracts directly

## Persistence Boundaries

SQLite is the canonical mutable state store.

Rules:

- queue state lives in SQLite, not YAML
- stdout/stderr logs live in files, not SQLite blobs
- SQLAlchemy models stay under infrastructure
- Pydantic models stay under domain
- Alembic owns schema evolution from the start

No module should treat ORM objects as public response objects.

## Runtime Ownership

`xqueue` owns only the artifacts it creates.

This applies to:

- SQLite files
- runtime files
- stdout/stderr logs
- generated wrappers
- managed `launchd` plists
- managed `systemd --user` unit files

`xqueue` must not mutate unmanaged system artifacts.

## Process Execution Model

Jobs are command-first and shell-first in v1.

Workers execute subprocesses and must manage process groups so timeout and
cancellation can terminate the whole command tree.

That logic belongs in services invoked by actions, not in CLI shells.

## Implementation Conventions

When adding code:

1. Put runnable code in `apps/` only if it is an entrypoint.
2. Put a use case in `libs/actions/` if it represents an operator-visible or
   system capability.
3. Put infrastructure integrations in `libs/services/` or `libs/infra/`
   depending on whether the concern is an abstract integration or a concrete
   low-level implementation.
4. Put response and validation schemas in `libs/domain/`.
5. Keep state-transition and orchestration logic out of app shells.

When in doubt, bias toward preserving the dependency direction and keeping app
surfaces thin.
