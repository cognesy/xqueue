# Job Model

This chapter is derived from the root `SPEC.md`.
`SPEC.md` remains the canonical source of truth.

## Core Model

The primary unit is a `job`.

A job is a request to execute one command with associated execution metadata.

### Job fields

- `id`
- `queue`
- `command`
- `shell`
- `cwd`
- `env`
- `priority`
- `timeout_seconds`
- `max_attempts`
- `created_at`
- `available_at`
- `state`
- `lease_expires_at`
- `worker_id`
- `attempt_count`
- `last_exit_code`
- `last_error`
- `cancel_requested_at`
- `created_by`

### Command-first model

`xq` exists to run CLI commands.

It should not model jobs as:

- Python callables
- import paths
- serialized functions
- task names plus argument blobs

The primary abstraction is one command-execution job with metadata.

This is deliberate and should remain a core design constraint.

### Execution model

Jobs are command-execution jobs, not callable references.

The default operator UX should be command-string based:

```sh
xq enqueue --queue agent --cwd /repo -- "python scripts/check_mailbox.py --agent writer-1"
```

Internally, the system may support one of two execution modes:

- shell mode
  - store one command string
  - execute with `/bin/sh -lc`
- exec mode
  - store exact argv
  - execute directly without shell expansion

For v1, shell mode is the primary mode and should be explicit and documented.

The design should not require argument splitting in the core model. A command
string is sufficient for the primary UX.

If direct exec mode is added later, it should be treated as an explicit advanced
execution mode, not the default operator model.

### Process model

Workers should execute jobs as child subprocesses and manage them via process
groups.

That is required so the system can:

- terminate a whole command tree on timeout
- terminate a whole command tree on operator cancellation
- avoid leaving orphaned subprocesses behind

The queue is responsible for process execution and observation, not for
embedding job logic inside the worker process.

## State Model

Jobs must have explicit durable states:

- `queued`
- `running`
- `succeeded`
- `failed`
- `retry_scheduled`
- `canceled`

Optional later states:

- `timed_out`
- `dead`

Each execution attempt should also be recorded separately so operators can see
attempt history even when the top-level job is retried multiple times.

State transitions should be explicit and constrained. The system should avoid
hidden status meanings.

Example lifecycle:

```text
queued -> running -> succeeded
queued -> running -> failed
queued -> running -> retry_scheduled -> queued
queued -> canceled
queued -> running -> canceled
```

## Main Capabilities

### Required in v1

- durable enqueue
- queue selection
- worker concurrency control
- atomic job claiming
- retries with delay
- per-job timeout
- cancellation of queued jobs
- cooperative stop for running jobs
- inspection via CLI
- machine-readable JSON output
- attempt history
- stdout/stderr capture
- stale lease recovery after worker crash

### Explicitly out of scope for v1

- distributed workers
- remote broker mode
- DAG dependencies
- cron-like scheduling
- web UI
- plugin framework
- exactly-once delivery semantics

## Engineering Constraints

The implementation should respect the following constraints from the start:

- SQLite must run in WAL mode
- SQLite access must use explicit transaction boundaries
- SQLite must use a sensible `busy_timeout`
- Alembic must be used for schema migrations from day one
- `platformdirs` must determine default config, state, runtime, and log paths
- Rich must only be used for `--output text`
- `--output json` must never depend on Rich formatting
- YAML must only be used for configuration, never for mutable queue state
- stdout/stderr logs must live in files, not database blobs
- Pydantic models must not be used as ORM models
- SQLAlchemy persistence models must remain separate from domain and output
  models
