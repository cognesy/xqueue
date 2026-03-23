# xqueue Specification

## Name

- project name: `xqueue`
- CLI name: `xq`

`xqueue` is a minimal, single-machine, CLI-first durable work queue for running
shell commands.

## Technology Baseline

The initial implementation should use:

- Python
- `uv` for environment and dependency management from day one
- Typer for the CLI surface
- Rich for human-readable text output
- Pydantic for data models
- PyYAML for YAML configuration parsing
- SQLAlchemy for database access
- Alembic for schema migrations
- `platformdirs` for default config, state, runtime, and log paths
- structlog for structured application logging
- pytest for automated testing

Additional implementation guidance:

- `uv` is mandatory, not optional
- project setup, dependency installation, local execution, and test workflows
  should all assume `uv`
- human-readable rendering must be cleanly separated from machine-readable JSON
  output
- database models and API/data models should remain separate concerns
- Rich must only affect `--output text`
- `--output json` must bypass presentation formatting entirely
- YAML is for static configuration, never for mutable queue state
- application logs should be structured and emitted through `structlog`
- prefer standard `subprocess` plus process groups over heavier execution
  machinery
- `psutil` is optional and should only be added if native process-group
  handling proves insufficient

## Context

`xqueue` exists to complement `xcron`.

The intended operating model is:

1. `xcron` runs a periodic command such as a mailbox poller
2. that command decides whether there is work to do
3. if work exists, it enqueues one or more command-execution jobs into `xq`
4. `xq` workers execute those jobs with explicit concurrency control

This system is intentionally local-first and single-machine. It is not intended
to be a distributed queue, a workflow engine, or a general-purpose task
platform.

## Problem Statement

The user needs a lightweight queue with these constraints:

- the queue must be fully operable via CLI
- the jobs are shell commands, not Python functions or serialized callables
- the system runs on one machine
- durability matters
- concurrency control matters
- inspection and cancellation matter
- no GUI or web UI is required or desired

Existing systems often miss one or more of these requirements:

- too heavy operationally
- not truly CLI-first
- tied to application-level function execution
- designed around distributed infrastructure

`xqueue` should solve the narrow local queueing problem with minimal machinery.

## Product Positioning

`xqueue` is:

- a local durable queue for command execution
- a CLI-first operator tool
- a small control plane for one-machine worker management
- a complement to `xcron`

`xqueue` is not:

- a distributed message broker
- a function execution framework
- a workflow engine or DAG runner
- a scheduler
- a replacement for OS process supervision

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

## CLI Requirements

The CLI is the primary interface, not a thin helper over a library.

Every important operation must be available from `xq`.

### Minimum command surface

```sh
xq enqueue --queue agent -- "check-mailbox --agent writer-1"
xq worker --queue agent --concurrency 4
xq jobs list
xq jobs list --state running
xq jobs show <job-id>
xq jobs cancel <job-id>
xq jobs retry <job-id>
xq jobs delete <job-id>
xq jobs tail <job-id>
xq jobs purge --queue <queue>
xq queues list
xq queues stats
xq queues pause <queue>
xq queues resume <queue>
xq workers list
xq workers stop <worker-id>
xq workers pause <worker-id>
xq workers resume <worker-id>
xq workers drain <worker-id>
xq config show
xq controller run
xq controller install
xq controller uninstall
xq controller start
xq controller stop
xq controller restart
xq controller status
xq health
xq doctor
xq recover stale-leases
xq db check
xq db vacuum
```

### CLI principles

- human-readable default output
- structured output is a first-class interface, not a debug feature
- every operator-facing command should support `--output text|json`
- `--output json` must be stable enough for automation via tools such as `jq`
- non-interactive by default
- stable exit codes
- explicit filtering and sorting

### Output contract

`xq` is intended to be operated by both humans and agents.

Because of that, machine-readable output must be part of the primary CLI design.

Commands that return data or mutation results should support:

```sh
--output text
--output json
```

Guidelines:

- `text` is optimized for humans
- `json` is optimized for automation
- `json` output should avoid presentation-only fields
- `json` output should use stable top-level shapes per command
- error output should remain structured where practical
- field naming should remain stable once released
- JSON output should be easy to compose with `jq`

Suggested JSON conventions:

- list commands return `{ "items": [...] }`
- detail commands return `{ "item": { ... } }`
- successful mutations return `{ "ok": true, "item": { ... } }`
- command collections may include `"meta"` for pagination or summary counts
- failures should return `{ "ok": false, "error": { ... } }` when practical

Suggested error shape:

```json
{
  "ok": false,
  "error": {
    "code": "not_found",
    "message": "job not found",
    "details": {}
  }
}
```

Examples:

```sh
xq jobs list --state queued --output json | jq
xq jobs show <job-id> --output json | jq
xq jobs cancel <job-id> --output json | jq
xq queues stats --output json | jq
```

## Configuration Model

Configuration should be optional and minimal.

The queue must remain operable without a configuration file when flags and
defaults are sufficient.

If a config file is used, YAML is the source format.

Configuration should cover static settings such as:

- database path
- log root
- runtime root
- default queue
- worker polling settings
- default timeout values
- cancel grace period

Configuration should not contain mutable queue state.

The CLI should expose:

```sh
xq config show --output json
```

Controller configuration should be static YAML, not mutable runtime state.

It should support named worker pools with fields such as:

- pool name
- queues served
- concurrency
- polling settings
- restart policy
- default timeout overrides

This configuration should be readable by both direct controller invocation and
platform service integration.

## Filesystem Layout

Default paths should be determined via `platformdirs`.

At minimum, the system should have stable locations for:

- config file
- SQLite database
- stdout/stderr logs
- pid or runtime files if needed

The implementation should not require operators to invent these paths manually
for normal use.

## Controller Model

`xq` should support two worker operating modes:

- direct mode
  - the operator runs `xq worker ...` manually
- controller mode
  - a long-lived `xq controller` process supervises one or more worker pools

The controller is not required for the queue to function, but it should be the
standard way to keep worker pools running continuously in the background.

Controller responsibilities:

- load static worker-pool configuration
- launch worker child processes
- restart failed workers according to policy
- expose controller and worker status via CLI
- shut workers down cleanly on stop/restart

The controller should supervise workers. It should not also become a scheduler.

The controller should also support graceful operational modes such as:

- pause intake
- drain workers
- graceful stop
- restart with configuration reload

## Platform Integration

`xq` should follow the same broad integration philosophy as `xcron`:

- keep platform-specific service-management logic behind dedicated services
- generate only explicit managed artifacts
- use deterministic machine-local state paths
- keep ownership boundaries strict

However, the native integration target is different from `xcron`.

`xcron` reconciles one-shot scheduled jobs, so it targets:

- macOS: `launchd`
- Linux: `cron`

`xq` needs a long-lived background controller, so the preferred service-manager
targets should be:

- macOS: `launchd` user agent
- Linux: `systemd --user`

`cron` is not an appropriate primary integration target for the `xq`
controller, because `cron` schedules one-shot commands rather than supervising
long-lived worker daemons.

`systemd` is common on Linux but must not be assumed to exist on every Linux
system.

Therefore the Linux strategy should be:

- primary integration target: `systemd --user`
- mandatory fallback: direct shell mode
- possible later adapter if needed: `OpenRC`

The project should not claim universal Linux daemon-manager support in v1.

### macOS

On macOS, `xq controller install` should generate and manage a `launchd`
LaunchAgent.

Expected approach:

- managed plist in `~/Library/LaunchAgents`
- label prefix such as `dev.xq.controller.`
- `RunAtLoad = true`
- `KeepAlive = true`
- `ProgramArguments` invoking `xq controller run`
- stdout/stderr paths under the managed `xq` state/log root

Lifecycle operations should map to `launchctl`:

- install/bootstrap
- enable
- kickstart or equivalent restart flow
- bootout/uninstall
- status inspection

### Linux

On Linux, `xq controller install` should generate and manage a user-scoped
`systemd` service unit.

Expected approach:

- managed unit file under the user systemd unit directory
- service name such as `xq-controller.service` or a profile-specific variant
- `ExecStart=` invoking `xq controller run`
- `Restart=on-failure` or similar
- working directory and environment set explicitly
- stdout/stderr routed to deterministic managed log files or journald according
  to the chosen policy

Lifecycle operations should map to `systemctl --user`:

- daemon-reload
- enable --now
- start
- stop
- restart
- status
- disable
- remove managed unit

### Fallback behavior

If the native service manager is unavailable or the operator chooses not to use
it, `xq controller run` and `xq worker ...` must still be usable directly from
the shell.

That direct mode is a fallback and a development path. It should not be the
only long-running deployment story.

### Explicit non-goals for v1 platform integration

The following are not required in v1:

- `OpenRC` integration
- `runit` integration
- `s6` integration
- claiming support for all Linux init systems

Those may be added later behind the same service-integration boundary if real
operator demand exists.

## Ownership Model

`xq` must only modify artifacts it owns.

Examples:

- `launchd` labels prefixed with `dev.xq.`
- managed plist files in a known directory
- managed `systemd --user` unit files with a stable naming convention
- generated runtime wrappers or helper scripts in the managed state directory

This follows the same safety rule used in `xcron`: never touch unmanaged native
artifacts.

## Worker Model

Workers are long-running local processes started by the operator.

Example:

```sh
xq worker --queue agent --queue maintenance --concurrency 4
```

Worker responsibilities:

- atomically lease runnable jobs
- spawn subprocesses for commands
- heartbeat while jobs are running
- capture stdout/stderr
- update attempt and job state
- honor timeout and cancel requests
- requeue or fail jobs when appropriate

Workers should support operational lifecycle states such as:

- active
- paused
- draining
- stopped

These states are distinct from job states and should be visible through CLI
inspection.

### Lease model

Job claiming must be transactionally safe.

The worker model should use leases rather than blind state flips.

At minimum:

- a worker claims one runnable job in a transaction
- the job becomes associated with that worker
- the lease has an expiry timestamp
- the worker renews the lease while the job is running
- another worker may recover the job if the lease becomes stale

This is the core crash-recovery mechanism.

Workers should heartbeat active leases while jobs are running.

### Worker crash recovery

If a worker dies unexpectedly:

- running jobs with stale leases must be detected
- those jobs must be requeued or marked failed according to policy
- recovery behavior must be visible in job history and events

The system should assume at-least-once delivery, not exactly-once execution.

## Queue Control Model

Queues are operator-visible resources.

At minimum, operators should be able to:

- list queues
- inspect queue depth and running counts
- pause a queue
- resume a queue
- purge queued jobs from a queue

Pausing a queue should prevent new jobs from being claimed while preserving
existing queued jobs.

Purging should affect only queued or retry-scheduled jobs, never silently remove
running jobs.

## Cancellation Semantics

Cancellation must be precise and unsurprising.

### Queued jobs

If a job has not started, canceling it should move it directly to `canceled`.

### Running jobs

Canceling a running job should:

1. mark cancellation as requested
2. signal the child process with `SIGTERM`
3. wait for a configurable grace period
4. escalate to `SIGKILL` if still running
5. record that the attempt ended due to operator cancellation

This is sufficient for local command execution. No more abstract cancellation
model is needed.

## Timeout Semantics

Timeout handling should mirror cancellation handling operationally.

If a running job exceeds its timeout:

1. record the timeout condition
2. send `SIGTERM` to the process group
3. wait for a configurable grace period
4. escalate to `SIGKILL` if needed
5. mark the attempt as timed out
6. either fail permanently or schedule a retry according to policy

Timeout and operator cancellation are different reasons and should remain
distinct in stored metadata.

## Retry and Failure Policy

Retries must be explicit and inspectable.

At minimum, the system should support:

- `max_attempts`
- retry delay
- optional backoff policy later

Failure outcomes should remain distinguishable:

- failed
- timed out
- canceled
- recovered after stale lease

The operator should be able to understand why a job did not succeed without
reading unstructured logs first.

An archived or dead-letter style state may be added later, but v1 can treat
permanently exhausted jobs as failed with attempt history preserved.

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

## Query and Inspection Model

Inspection must work well for both humans and agents.

The system should support filtering by at least:

- job id
- queue
- state
- worker id
- creation time
- availability time

Queue and worker inspection should be first-class operations, not debug tools.

Examples:

```sh
xq jobs list --queue agent --state running --output json
xq workers list --output json
xq queues stats --output json
```

## Health and Recovery

Daily operations require explicit health and recovery commands.

At minimum, the CLI should support:

- `xq health`
- `xq doctor`
- `xq recover stale-leases`
- `xq db check`
- `xq db vacuum`

These commands should help operators and agents answer questions such as:

- is the database healthy?
- are workers heartbeating?
- are there stale leases?
- are queues paused?
- does local state need maintenance?

## Exit Codes

CLI exit codes should be stable and intentional.

At minimum, the implementation should reserve distinct non-zero exit codes for:

- validation error
- not found
- conflict or invalid state transition
- runtime execution error
- timeout or interrupted operation where applicable

This matters for agent automation and shell scripting.

## Packaging and Execution Environment

Daily operations require a clear install and runtime story.

The project should define:

- how `xq` is installed with `uv`
- how platform service units invoke the correct `uv`-managed environment
- whether a small stable wrapper entrypoint script is generated for services

Native service-manager integration must not depend on fragile ad hoc shell
initialization.

## Relationship to xcron

The intended split is:

- `xcron` decides when to run something
- `xq` decides how queued command work is executed and observed

Example:

```sh
xcron -> poll-mailbox -> xq enqueue --queue agent -- "run-agent --task 123"
```

This keeps scheduling separate from queue execution and keeps both tools small.

When background workers should remain continuously available, `xq` should use
native service managers rather than trying to stretch `xcron` into daemon
supervision.

## Implementation Direction

The implementation should follow the same general philosophy as `xcron`:

- thin CLI shells in `apps/`
- reusable logic in `libs/`
- explicit schemas and resources in `resources/`
- docs in `docs/`

Suggested initial layout:

```text
apps/
  cli/
libs/
  actions/
  domain/
  infra/
  services/
resources/
  schemas/
docs/
```

The Python project tooling should be designed around `uv` from the start:

- `uv sync`
- `uv run xq ...`
- `uv run pytest`
- `uv run alembic upgrade head`

The project should not assume ad hoc `pip` workflows as the primary path.

Schema evolution should use Alembic from the beginning even if the initial
schema is small.

## Testing Direction

The project should include tests for:

- CLI behavior
- JSON output shapes
- state transitions
- concurrent worker claims
- timeout handling
- cancellation handling
- stale lease recovery
- SQLite persistence across process restarts
- pause, resume, and drain semantics
- queue purge behavior
- health and recovery commands
- exit-code behavior
- controller configuration loading
- platform service artifact rendering

`pytest-xdist` is optional and should only be introduced if the test suite grows
enough to justify parallel execution.

## Main Implementation Risks

The main risks are not the choice of CLI or ORM libraries.

The main risks are:

- atomic job claim logic
- worker crash recovery
- timeout and cancellation behavior for process groups
- keeping JSON output stable for agent automation

## First Milestone

The first useful milestone is:

1. enqueue command jobs into SQLite
2. run one worker process
3. support `queued`, `running`, `succeeded`, `failed`, `canceled`
4. support retries and timeouts
5. expose `jobs list/show/cancel/retry` via CLI
6. emit JSON for automation

If this milestone is solid, everything else can remain incremental.
