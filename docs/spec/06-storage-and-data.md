# Storage And Data

This chapter is derived from the root `SPEC.md`.
`SPEC.md` remains the canonical source of truth.

## Storage Backend Decision

### Recommendation

Use SQLite as the primary durable backend.

### Why SQLite

SQLite is the right default for this project because it gives:

- durable local storage
- transactions
- atomic claim/update behavior
- filtering and indexing for CLI queries
- straightforward crash recovery bookkeeping
- one-file operational simplicity

This is the simplest storage engine that still behaves like a queue, not like a
log file.

### SQLite operational requirements

The implementation should assume:

- WAL mode
- explicit transaction boundaries
- sensible `busy_timeout`
- indexes for common list and claim queries

Database access should be designed for modest local concurrency, not high-scale
distributed load.

### Why not JSONL as the primary backend

JSONL is attractive because it is simple and inspectable, but it breaks down
quickly for queue state management:

- no transactions
- hard to atomically claim one job among multiple workers
- awkward cancellation updates
- awkward retries and lease expiry updates
- poor query ergonomics for `list`, `stats`, and filtering
- compaction and rewrite complexity once records mutate

JSONL works well as:

- an append-only event log
- an export format
- a debug or audit artifact

JSONL does not work well as the canonical mutable queue state once you need
durable claims, retries, and cancellation.

### Decision

For v1:

- canonical state store: SQLite
- optional audit/export format: JSONL

## Data Boundaries

The codebase should keep these concerns separate:

- SQLAlchemy models for persistence
- Pydantic models for CLI input, domain output, and JSON responses
- Rich renderers for `text` output only

No Rich or presentation-oriented formatting should leak into JSON generation.

## Suggested Schema

At minimum:

- `jobs`
- `attempts`
- `workers`
- `events`

### `jobs`

Stores current state and operator-facing metadata.

It should also be able to represent queue pause interactions, retry scheduling,
and cancellation requests cleanly.

### `attempts`

Stores one row per execution attempt, including timing, exit code, and log
paths.

### `workers`

Stores worker identity, heartbeat, queues served, and process metadata.

It should also record operational state such as active, paused, or draining.

### `events`

Optional append-only audit trail for state transitions such as:

- enqueued
- leased
- started
- stdout appended
- stderr appended
- retry scheduled
- canceled
- succeeded
- failed

The `events` table can later support JSONL export, but the database remains the
source of truth.

## Logging

Each attempt should have separate stdout/stderr log files on disk.

The database should store references to those paths and small structured
summaries, not full unbounded logs inline.

`xq jobs tail <job-id>` should read from these log files rather than from
database blobs.

Application-level controller and worker logs should be emitted via `structlog`
and remain separate from per-job stdout/stderr capture.

## Reliability Model

The system should aim for at-least-once execution semantics on one machine.

That means:

- if a worker dies after leasing but before completion, jobs may be retried
- commands must therefore be assumed to be retriable or idempotent where needed

Exactly-once execution is explicitly not a goal.

This implies operators should treat queued commands as retriable or idempotent
where needed.

## Retention and Cleanup

The system needs explicit retention policies for daily operations.

At minimum, the design should account for:

- old completed job retention
- old attempt retention
- old event retention
- per-job log retention
- database maintenance such as vacuuming

Cleanup should be explicit and operator-controlled. Retention should not silently
remove data without a defined policy.
