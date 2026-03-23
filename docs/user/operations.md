# Operations

## Runtime Model

`xqueue` stores mutable queue state in SQLite and writes attempt logs to files.
In repository-local development mode, the important paths are:

- `instance/xqueue.db`
- `instance/run/`
- `instance/logs/`
- `instance/config.yaml`

In normal installed usage, the same paths resolve through `platformdirs`. Use
`xq config show --output json` to confirm the effective locations on a machine.

The delivery model is at-least-once. A job can be retried after worker failure
or stale lease recovery, so commands should be safe to run more than once.

## JSON Output And Logs

Operator commands support `--output text|json`.

- `--output text` is the default human-readable mode.
- `--output json` writes the command result envelope to `stdout`.
- application logs use `structlog` and are emitted as JSON on `stderr`.

For automation, consume `stdout` as the API payload and treat `stderr` as
structured logs.

Stable JSON shapes:

- list commands: `{ "items": [...] }`
- detail commands: `{ "item": { ... } }`
- successful mutations: `{ "ok": true, "item": { ... } }`
- failures: `{ "ok": false, "error": { ... } }`

## Enqueue Jobs

The primary v1 model is a shell command string:

```sh
uv run xq enqueue \
  --workspace-instance \
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
  --workspace-instance \
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
root.

Important constraint:

- `--concurrency > 1` is only supported together with `--continuous` and
  `--execute-claimed`

## Inspect Jobs

List jobs:

```sh
uv run xq jobs list --workspace-instance --queue agent --state queued --output json
```

Filter by creation/availability windows and choose a sort order:

```sh
uv run xq jobs list \
  --workspace-instance \
  --queue agent \
  --created-after 2026-03-22T20:30:00Z \
  --available-before 2026-03-22T21:00:00Z \
  --sort available-desc \
  --output json
```

Show one job, including attempts and events:

```sh
uv run xq jobs show <job-id> --workspace-instance --output json
```

The job detail view is the main inspection surface for:

- current state
- assigned worker
- timeout and cancellation metadata
- attempt history
- log file paths
- recovery events

Tail the latest attempt stderr:

```sh
uv run xq jobs tail <job-id> --workspace-instance --output json
```

Tail another stream or attempt:

```sh
uv run xq jobs tail <job-id> \
  --workspace-instance \
  --stream stdout \
  --attempt-number 1 \
  --lines 50 \
  --output json
```

## Cancel, Retry, Delete, And Purge

Cancel a queued job immediately:

```sh
uv run xq jobs cancel <job-id> --workspace-instance
```

For a running job, cancellation is cooperative:

1. `xqueue` records the request
2. the worker sends `SIGTERM` to the subprocess group
3. the worker waits for the grace period
4. the worker escalates to `SIGKILL` if needed

Retry a failed or canceled job without deleting history:

```sh
uv run xq jobs retry <job-id> --workspace-instance
```

Delete a non-running job and its persisted history:

```sh
uv run xq jobs delete <job-id> --workspace-instance --output json
```

`jobs delete` is intended for cleanup. Running jobs are rejected explicitly.

Purge only queued or retry-scheduled jobs from a queue:

```sh
uv run xq jobs purge --queue agent --workspace-instance
```

## Queue And Worker Controls

Pause or resume a queue:

```sh
uv run xq queues pause agent --workspace-instance
uv run xq queues resume agent --workspace-instance
```

Inspect queue state and counts:

```sh
uv run xq queues list --workspace-instance --output json
uv run xq queues stats --workspace-instance --output json
```

Inspect or control worker state:

```sh
uv run xq workers list --workspace-instance --output json
uv run xq workers drain <worker-id> --workspace-instance
uv run xq workers stop <worker-id> --workspace-instance
```

Worker states are separate from job states:

- `active`
- `paused`
- `draining`
- `stopped`

## Controller Mode

Controller mode supervises configured worker pools. It does not schedule jobs.

Example `instance/config.yaml`:

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
uv run xq controller run --workspace-instance --controller-id default
```

Inspect or control it:

```sh
uv run xq controller status --workspace-instance --output json
uv run xq controller pause-intake --workspace-instance
uv run xq controller resume-intake --workspace-instance
uv run xq controller drain --workspace-instance
uv run xq controller restart --workspace-instance
uv run xq controller stop --workspace-instance
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
uv run xq controller install --workspace-instance --platform launchd
uv run xq controller start --workspace-instance --platform launchd
uv run xq controller status --workspace-instance --platform launchd --output json
```

Only service definitions owned by `xqueue` are managed.

## Health, Recovery, And Maintenance

High-level health:

```sh
uv run xq health --workspace-instance --output json
```

Detailed diagnostics:

```sh
uv run xq doctor --workspace-instance --output json
```

Recover stale leases after a worker crash:

```sh
uv run xq recover stale-leases --workspace-instance --output json
```

Database maintenance:

```sh
uv run xq db check --workspace-instance --output json
uv run xq db vacuum --workspace-instance --output json
```

Run explicit retention cleanup only when you intend to prune old history:

```sh
uv run xq db cleanup-retention \
  --workspace-instance \
  --older-than-hours 168 \
  --attempts \
  --events \
  --logs \
  --yes \
  --output json
```

This cleanup is explicit and operator-controlled. It does not run automatically.
Pruning old attempts can reduce detailed history while keeping top-level job
rows and summary metadata in place.

`recover stale-leases` is central to the reliability model. If a worker dies
after claiming a job, the job may be requeued or failed based on the retry
policy, and the recovery result is recorded in job history.

## Troubleshooting

If a job appears stuck in `running`:

1. inspect it with `xq jobs show <job-id> --output json`
2. inspect worker state with `xq workers list --output json`
3. run `xq health` or `xq doctor`
4. run `xq recover stale-leases` if the worker heartbeat is stale

If automation needs clean JSON payloads:

1. use `--output json`
2. read `stdout` for the command payload
3. keep `stderr` separate because it contains `structlog` action logs

If the runtime location is unclear:

1. run `xq config show --output json`
2. confirm `database_path`, `runtime_root`, and `log_root`

If the controller is managed by the OS service manager:

1. use `xq controller status --platform ...`
2. confirm the owned service artifact path in the returned payload
3. check controller logs under the resolved log root
