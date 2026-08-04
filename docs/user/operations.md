# Operations

## Runtime Model

`xqueue` stores mutable queue state in SQLite and writes attempt logs to files.
Both live in one workspace directory, created by `xq workspace init`:

- `.xqueue/marker.toml` -- what makes the directory a workspace
- `.xqueue/config.yaml`
- `.xqueue/xqueue.db`
- `.xqueue/run/`
- `.xqueue/logs/`

`init` migrates the database to the current schema, so the workspace is ready
to enqueue into as soon as the command returns. Migrating is idempotent: a
second `init` reports the database as retained and leaves it untouched. If
something that is not a SQLite database already occupies `.xqueue/xqueue.db`,
`init` reports it as a conflicting path rather than migrating or removing it.

Every command finds that directory by walking up from the working directory.
Outside a workspace the same paths resolve under the machine-wide instance:
`XQUEUE_HOME`, or `~/.xqueue/`. Use `xq -o json config show` to confirm the
effective locations on a machine.

The delivery model is at-least-once. A job can be retried after worker failure
or stale lease recovery, so commands should be safe to run more than once.

## Configuration

Settings come from several places. Later entries win over earlier ones:

1. the defaults shipped with `xqueue`
2. `--config <file>` (or `XQUEUE_CONFIG_PATH`), which *replaces* those defaults
   rather than layering over them
3. `--env <name>` (or `XQUEUE_ENV`), a shipped overlay such as `staging`,
   layered over the defaults
4. your user config directory
5. `.xqueue/config.yaml` in the workspace
6. environment variables, one per setting: `XQUEUE_WORKER__RETRY_DELAY_SECONDS`
   sets `worker.retry_delay_seconds`. The doubled underscore separates the
   section from the field, and a variable without one is not a setting.
7. `--set worker.retry_delay_seconds=30`, repeatable

`xq -o json config show` prints the result together with a `layers` list saying
which of those existed and which actually contributed, which is the fastest way
to find out why a value is not what you expected:

```sh
uv run xq -o json config show
uv run xq --set worker.poll_interval_seconds=0.5 -o json config show
```

`XQUEUE_HOME`, `XQUEUE_ROOT`, and `XQUEUE_DB_PATH` are not settings. They are
answered before configuration is read, and they choose *where* the workspace is
rather than what is in it.

A file that will not load, a key that is not a setting, or a value out of range
stops the command with an error envelope and exit code 2. Pass `-o json` before
the subcommand to see one as JSON: the failure happens while the command is
starting up, before its own `-o` has been read.

## Output Modes And Logs

Operator commands support `-o` / `--output` with:

- `toon` as the default machine-friendly mode
- `json` for stable structured envelopes
- `jsonl` for item-by-item streaming where supported
- `text` for human-readable output

Rules:

- `stdout` is the structured API payload
- application logs use `structlog` and are emitted as JSON on `stderr`.
- raw command stdout/stderr stay in per-attempt log files.
- concise job lifecycle events are written as JSONL beside those raw logs.
- Rich is only used for `-o text`

For automation, consume `stdout` as the API payload and treat `stderr` as
structured logs.

Logging defaults live in `resources/logging/default.yaml`. Use overrides when
you need a different local diagnostic view:

```sh
XQUEUE_LOG_LEVEL=DEBUG XQUEUE_LOG_FORMAT=console uv run xq health
XQUEUE_LOG_LEVEL=INFO XQUEUE_LOG_FORMAT=json uv run xq jobs list -o json
```

Stable JSON shapes:

- list commands: `{ "items": [...] }`
- detail commands: `{ "item": { ... } }`
- successful mutations: `{ "ok": true, "item": { ... } }`
- failures: `{ "ok": false, "error": { ... } }`

Useful examples:

```sh
uv run xq jobs list
uv run xq -o json jobs show <job-id>
uv run xq --fields id,state jobs list
```

## Enqueue Jobs

The primary v1 model is a shell command string:

```sh
uv run xq enqueue \
  --queue agent \
  --cwd /repo \
  --timeout-seconds 300 \
  --max-attempts 3 \
  --env AGENT_NAME=writer-1 \
  -- /bin/sh -lc 'python scripts/check_mailbox.py --agent writer-1'
```

Important options:

- `--queue` selects the queue.
- `--cwd` sets the subprocess working directory.
- `--timeout-seconds` applies a per-job timeout.
- `--max-attempts` controls retry eligibility.
- `--env KEY=VALUE` adds environment variables.

## Run Workers

Direct worker mode is the simplest operating path:

```sh
uv run xq worker \
  --queue agent \
  --concurrency 2 \
  --continuous \
  --execute-claimed
```

Important behavior:

- claims are transactional
- in direct continuous mode, one worker process can keep up to `--concurrency`
  jobs in flight at once
- workers heartbeat while running
- commands run in their own process groups
- stdout and stderr are written to per-attempt files
- timeout and cancellation terminate the full process group

Useful options:

- `--concurrency`
- `--lease-seconds`
- `--poll-interval-seconds`
- `--default-timeout-seconds`
- `--cancel-grace-period-seconds`
- `--retry-delay-seconds`

Attempt logs are stored under `logs/jobs/<job-id>/` for the resolved runtime
root. Each attempt writes:

- `attempt-0001.stdout.log` for raw command stdout
- `attempt-0001.stderr.log` for raw command stderr
- `attempt-0001.events.jsonl` for operational lifecycle events

The JSONL event stream records claim/start/finish and terminal outcomes with
timestamps, queue, worker id, attempt id, command/cwd, exit code, duration,
stdout/stderr paths, and propagated `XPM_*`, `XQUEUE_*`, or `XCRON_*`
correlation environment values.

Important constraint:

- `--concurrency > 1` is only supported together with `--continuous` and
  `--execute-claimed`

## Inspect Jobs

List jobs:

```sh
uv run xq -o json jobs list --queue agent --state queued
```

Filter by creation/availability windows and choose a sort order:

```sh
uv run xq jobs list \
  --queue agent \
  --created-after 2026-03-22T20:30:00Z \
  --available-before 2026-03-22T21:00:00Z \
  --sort available-desc \
  -o json
```

Show one job, including attempts and events:

```sh
uv run xq -o json jobs show <job-id>
```

The job detail view is the main inspection surface for:

- current state
- assigned worker
- timeout and cancellation metadata
- attempt history
- stdout, stderr, and event log file paths
- recovery events

Tail the latest attempt stderr:

```sh
uv run xq -o json jobs tail <job-id>
```

Tail another stream or attempt:

```sh
uv run xq jobs tail <job-id> \
  --stream stdout \
  --attempt-number 1 \
  --lines 50 \
  -o json
```

## Cancel, Retry, Delete, And Purge

Cancel a queued job immediately:

```sh
uv run xq jobs cancel <job-id>
```

For a running job, cancellation is cooperative:

1. `xqueue` records the request
2. the worker sends `SIGTERM` to the subprocess group
3. the worker waits for the grace period
4. the worker escalates to `SIGKILL` if needed

Retry a failed or canceled job without deleting history:

```sh
uv run xq jobs retry <job-id>
```

Delete a non-running job and its persisted history:

```sh
uv run xq -o json jobs delete <job-id>
```

`jobs delete` is intended for cleanup. Running jobs are rejected explicitly.

Purge only queued or retry-scheduled jobs from a queue:

```sh
uv run xq jobs purge --queue agent
```

## Queue And Worker Controls

Pause or resume a queue:

```sh
uv run xq queues pause agent
uv run xq queues resume agent
```

Inspect queue state and counts:

```sh
uv run xq -o json queues list
uv run xq -o json queues stats
```

Inspect or control worker state:

```sh
uv run xq -o json workers list
uv run xq workers drain <worker-id>
uv run xq workers stop <worker-id>
```

Worker states are separate from job states:

- `active`
- `paused`
- `draining`
- `stopped`

## Controller Mode

Controller mode supervises configured worker pools. It does not schedule jobs.

Prefer the pool-management commands over hand-editing YAML:

```sh
uv run xq controller pools ensure agent --queue agent --concurrency 2
uv run xq -o json controller pools list
uv run xq controller pools remove agent
```

Changed pool config reports `restart_required`; restart the controller before
expecting running controller processes to use the new definition.

Example `.xqueue/config.yaml`:

```yaml
controller:
  pools:
    agent:
      queues: [agent]
      concurrency: 2
      poll_interval_seconds: 1.0
      lease_seconds: 30
      restart_policy: on-failure
```

Run the controller directly:

```sh
uv run xq controller run --controller-id default
```

Inspect or control it:

```sh
uv run xq -o json controller status
uv run xq controller pause-intake
uv run xq controller resume-intake
uv run xq controller drain
uv run xq controller restart
uv run xq controller stop
```

`controller pause-intake` is distinct from `queues pause`:

- queue pause blocks claims for one named queue
- controller pause-intake flips supervised workers to `paused` so direct
  controller mode stops taking new work across the configured pools
- already running jobs are allowed to finish

Managed service mode is also available:

- macOS: `launchd`
- Linux: `systemd --user`

Examples:

```sh
uv run xq controller install --platform launchd
uv run xq controller start --platform launchd
uv run xq -o json controller status --platform launchd
```

Only service definitions owned by `xqueue` are managed.

## Health, Recovery, And Maintenance

High-level health:

```sh
uv run xq -o json health
```

Detailed diagnostics:

```sh
uv run xq -o json doctor
```

Recover stale leases after a worker crash:

```sh
uv run xq -o json recover stale-leases
```

Database maintenance:

```sh
uv run xq -o json db check
uv run xq -o json db vacuum
```

Run explicit retention cleanup only when you intend to prune old history:

```sh
uv run xq db cleanup-retention \
  --older-than-hours 168 \
  --attempts \
  --events \
  --logs \
  --yes \
  -o json
```

This cleanup is explicit and operator-controlled. It does not run automatically.
Pruning old attempts can reduce detailed history while keeping top-level job
rows and summary metadata in place.

`recover stale-leases` is central to the reliability model. If a worker dies
after claiming a job, the job may be requeued or failed based on the retry
policy, and the recovery result is recorded in job history.

## Troubleshooting

If a job appears stuck in `running`:

1. inspect it with `xq -o json jobs show <job-id>`
2. inspect worker state with `xq -o json workers list`
3. run `xq health` or `xq doctor`
4. run `xq recover stale-leases` if the worker heartbeat is stale

If automation needs a minimal machine payload:

1. use `-o json` or accept the default TOON output
2. read `stdout` for the command payload
3. keep `stderr` separate because it contains `structlog` action logs

If the runtime location is unclear:

1. run `xq -o json config show`
2. confirm `database_path`, `runtime_root`, and `log_root`

If the controller is managed by the OS service manager:

1. use `xq controller status --platform ...`
2. confirm the owned service artifact path in the returned payload
3. check controller logs under the resolved log root
