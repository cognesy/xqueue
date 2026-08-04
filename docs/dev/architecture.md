# Architecture

## Purpose

This document defines the current repository layout, dependency direction, and
runtime ownership for `xqueue`. `SPEC.md` remains the product source of truth.

## Core Shape

The library is capability-oriented and has one public root:

```text
xqueue.Xqueue
  ├── jobs
  ├── queues
  ├── workers
  ├── controller
  ├── maintenance
  └── workspace
```

`Xqueue.open(...)` creates one owned runtime. Facets are lazy and cached; using
the client as a context manager closes SQLite resources deterministically.

The dependency direction is:

```text
apps/cli -> capability APIs -> capability actions and ports -> adapters
                         \-> core invariants
runtime composition ----------------------------------------^
```

The CLI and SDK share this graph. There is no second set of CLI-only use cases.

## Repository Layout

- `apps/cli/`: Typer shells, envelopes, output contracts, and renderers
- `libs/jobs/`: enqueue, inspection, logs, pruning, and job transitions
- `libs/queues/`: queue inspection and intake control
- `libs/workers/`: claiming, attempts, execution, process groups, and workers
- `libs/controller/`: pools, supervision, and launchd/systemd adapters
- `libs/maintenance/`: health, recovery, metrics, retention, and DB maintenance
- `libs/workspace/`: configuration, runtime paths, hooks, and local reset
- `libs/core/`: only cross-capability errors and date/time helpers; each
  capability owns its own `models.py`
- `libs/runtime/`: lifecycle, composition, resources, and structured logging
- `libs/adapters/sqlite/`: SQLAlchemy ORM, engine, and session implementation
- `resources/`: Alembic migrations and packaged static assets
- `tests/`: behavior and boundary verification
- `.xqueue/`: the workspace directory -- marker, config, database,
  run and log roots -- created by `xq workspace init`

The former global `actions`, `domain`, `infra`, and `services` packages are not
compatibility surfaces and must remain physically absent.

## Capability Boundary

Each capability may contain the pieces it needs: public models, a typed API
facet, actions, ports, stores, and focused mechanics. A capability should expose
workflow-shaped operations rather than generic repositories or managers.

Cross-capability code belongs in `core` only when it is a stable invariant used
by multiple capabilities. Concrete application wiring belongs in `runtime`, not
in module-level singletons.

## CLI Boundary

`apps/cli/` owns all shell concerns:

- Typer parsing and command registration
- stable list, detail, mutation, and error envelopes
- output field selection
- TOON, JSON, JSONL, text, and tmux rendering
- exit-code translation

Rich is used only for text output. Machine-readable paths bypass Rich. Library
facets return typed values and never import `xqueue_cli`.

## Persistence Boundary

SQLite is the canonical mutable state store. The engine, the session factory,
and the ORM models are sealed inside `libs/adapters/sqlite/`. SQLAlchemy query
construction is not sealed: it is allowed in the capability persistence modules
named by the `xqueue-no-sqlalchemy-outside-persistence` Semgrep allowlist and in
the composition root, and is an error in every `api.py`, `models.py`, and
`actions.py`, in `libs/core/`, and in the CLI. ORM objects are never public SDK
or CLI response types.
Pydantic models stay separate from ORM models. Alembic owns schema evolution,
and the SQLite engine enables WAL, foreign keys, explicit transactions, and a
sensible busy timeout.

Job stdout and stderr stay in owned files, not database blobs.

## Configuration Boundary

Configuration is composed once, by `libs/workspace/loader.py`, which is the only
module that may import the configuration library. Callers pass a `ConfigInputs`
-- a replacement file, an environment name, and dotted-path overrides -- and get
an `EffectiveConfig` back. No library type reaches a caller, and a failure to
compose surfaces as `ConfigurationError`, never as a foreign exception.

The layer order, base first, is:

1. the packaged `config.default.yaml`, or an explicit file that *replaces* it
   (`--config`, `XQUEUE_CONFIG_PATH`, or the SDK's `config_path`)
2. a named environment overlay layered over the default (`--env`, `XQUEUE_ENV`)
3. the user config directory
4. `<workspace>/config.yaml`
5. environment variables, which are read only if they carry the nested
   delimiter `__` -- so the flat `XQUEUE_HOME`, `XQUEUE_ROOT`, `XQUEUE_DB_PATH`,
   `XQUEUE_LOG_LEVEL`, and `XQUEUE_LOG_FORMAT` are invisible to this layer
6. `--set path=value`, or the SDK's `overrides`

`EffectiveConfig.layers` reports that chain and which entries applied, so
`xq config show` can say where a value came from without a second mechanism.

Two rules keep this shape: environment access is confined to the resolver, the
loader, and the process adapters; and the workspace root is decided once, in
runtime composition, then handed down -- a capability that imports the resolver
could answer "which workspace am I in" differently from the runtime that opened
it.

## State Ownership

Which module may write which table is recorded in
[`plane-map.md`](plane-map.md), and today the answer is not one module per
table. `queues`, `workers`, the metrics file, and the launchd and systemd
artifacts each have a single writer. The `jobs` table does not: it is written
by `jobs/store.py`, `jobs/pruning.py`, `queues/store.py`, `workers/store.py`,
`workers/attempts.py`, `maintenance/recovery.py`, and `maintenance/retention.py`.
The `attempts` table is written by four of those. `events` is append-only from
five modules, which is acceptable for a log.

Each of those writes is a legitimate job-lifecycle transition — claim,
complete, cancel, expire a lease, delete — inside one action's transaction
against one SQLite file with WAL and `foreign_keys=ON`, so the risk today is
low. It is not zero, and it grows with every capability that finds it
convenient to reach for `JobModel`: the SQLAlchemy allowlist governs which
modules may build queries and says nothing about which tables each may touch.

`maintenance/health.py` imports `WorkerModel` but only reads it
(`libs/maintenance/health.py:148`), so it is not a second writer.

Fixing this is owned by `xqueue-57w.1`, not by the module that found it. The
smallest useful seam is one declared writer per table, enforced the way the
SQLAlchemy allowlist is enforced — a rule naming which persistence module may
import which ORM model, verified by planting a `JobModel` import in a
capability that does not own it.

## Process And Platform Boundaries

Worker subprocess and process-group behavior belongs to the workers capability.
Timeout and cancellation must target the entire process group. Controller child
process and service-manager behavior belongs to the controller capability.

The controller supervises worker pools; it is not a scheduler. Native adapters
modify only launchd or systemd artifacts generated and owned by `xqueue`.

## Enforced Rules

Ruff, Import Linter, the Python AST boundary checker, Semgrep, and explicit
absence tests enforce:

- core independence
- no library dependency on the CLI
- no direct CLI dependency on SQLite adapters
- Rich and Typer confinement
- SQLAlchemy confinement to the SQLite adapter
- subprocess confinement to worker/controller process adapters
- the configuration library reachable only from `xqueue.workspace.loader`
- environment reads confined to workspace resolution, the config loader, and
  the process adapters
- capabilities never importing the workspace resolver: a decided root is passed
  down, never rediscovered
- absence of the former global technical-layer packages

When adding behavior, start in the capability whose operator concept owns it,
add or reuse a narrow port for an external boundary, wire the concrete adapter
once in runtime composition, and keep presentation in the CLI.
