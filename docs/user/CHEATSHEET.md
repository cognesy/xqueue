# XQueue Cheat Sheet

Quick operator reference for the currently shipped CLI.

Run `xq workspace init` once in a project and every command below finds that
workspace by walking up from the working directory. Outside a workspace the
same commands use the machine-wide instance at `XQUEUE_HOME`, or `~/.xqueue`.

`--workspace-instance` is the deprecated spelling of "the workspace right
here". It still works, and it now means `.xqueue/` rather than the old
`instance/`.

## Basic Setup

```sh
uv sync                        # dev group includes the cli extra
uv tool install "xqueue[cli]"  # or, as an installed tool
uv run xq workspace init       # creates ./.xqueue/ with a marker and config
uv run xq --help
uv run xq
uv run xq -o json config show
uv run --project ../xqa --all-packages xqa doctor --root . --format json
uv run --project ../xqa --all-packages xqa mechanism verify --format json
uvx ruff check apps libs tests scripts
uv run python scripts/check_architecture.py
uv run pytest
```

## Configuration

```sh
uv run xq -o json config show                 # effective values plus `layers`
uv run xq --config ./other.yaml config show   # replaces the shipped defaults
uv run xq --env staging config show           # overlay, layered over them
uv run xq --set worker.retry_delay_seconds=30 -o json config show
XQUEUE_WORKER__RETRY_DELAY_SECONDS=30 uv run xq -o json config show
```

Precedence, lowest first: shipped defaults (or `--config`, which replaces them)
-> `--env` overlay -> user config -> `.xqueue/config.yaml` -> environment ->
`--set`. Environment variables need the doubled underscore to be settings;
`XQUEUE_HOME`, `XQUEUE_ROOT`, and `XQUEUE_DB_PATH` choose the workspace instead.

Configuration failures exit 2. Put `-o json` before the subcommand to see the
envelope: they happen before the subcommand's own `-o` is read.

## Enqueue Jobs

```sh
uv run xq enqueue \
  --queue agent \
  -- /bin/sh -lc 'echo hello from xqueue'
```

With more execution options:

```sh
uv run xq enqueue \
  --queue agent \
  --cwd /repo \
  --timeout-seconds 300 \
  --max-attempts 3 \
  --env AGENT_NAME=writer-1 \
  -- /bin/sh -lc 'python scripts/check_mailbox.py --agent writer-1'
```

## Inspect Jobs

```sh
uv run xq jobs list
uv run xq -o json jobs list --queue agent --state queued
uv run xq -o json jobs show <job-id>
uv run xq -o json jobs tail <job-id>
uv run xq jobs tail <job-id> \
  --stream stdout --attempt-number 1 --lines 50
uv run xq --fields id,state jobs list
```

`jobs show` includes per-attempt `stdout_path`, `stderr_path`, and
`event_log_path`. The event log is JSONL with concise lifecycle events such as
`job.claimed`, `job.started`, `job.finished`, `job.failed`,
`job.retry_scheduled`, `job.timed_out`, and `job.canceled`.

Filter and sort:

```sh
uv run xq jobs list \
  --queue agent \
  --created-after 2026-03-22T20:30:00Z \
  --available-before 2026-03-22T21:00:00Z \
  --sort available-desc \
  -o json
```

## Control Jobs

```sh
uv run xq jobs cancel <job-id>
uv run xq jobs retry <job-id>
uv run xq -o json jobs delete <job-id>
uv run xq jobs purge --queue agent
```

## Run Workers

One-shot claim:

```sh
uv run xq -o json worker --queue agent
```

Execute claimed work:

```sh
uv run xq worker \
  -o json \
  --queue agent \
  --execute-claimed
```

Continuous direct worker with real concurrency:

```sh
uv run xq worker \
  --queue agent \
  --concurrency 2 \
  --continuous \
  --execute-claimed
```

`--concurrency > 1` is only supported with `--continuous --execute-claimed`.

Useful worker options:

```sh
--lease-seconds
--poll-interval-seconds
--default-timeout-seconds
--cancel-grace-period-seconds
--retry-delay-seconds
```

## Queue And Worker Controls

```sh
uv run xq -o json queues list
uv run xq -o json queues stats
uv run xq queues pause agent
uv run xq queues resume agent

uv run xq -o json workers list
uv run xq workers pause <worker-id>
uv run xq workers resume <worker-id>
uv run xq workers drain <worker-id>
uv run xq workers stop <worker-id>
```

## Controller Mode

Run directly:

```sh
uv run xq controller pools ensure agent --queue agent
uv run xq -o json controller pools list
uv run xq controller run --controller-id default
uv run xq -o json controller status
```

Direct-mode control:

```sh
uv run xq controller pause-intake
uv run xq controller resume-intake
uv run xq controller drain
uv run xq controller restart
uv run xq controller stop
```

Managed mode:

```sh
uv run xq controller install --platform launchd
uv run xq controller start --platform launchd
uv run xq -o json controller status --platform launchd
uv run xq controller restart --platform launchd
uv run xq controller stop --platform launchd
uv run xq controller uninstall --platform launchd
```

Changing `controller.pools` requires a controller restart before running
controller processes use the new pool definition. Use `controller pools remove
<name>` to delete a configured pool.

`pause-intake` is controller-wide for direct mode. `queues pause` is per queue.

## Health And Recovery

```sh
uv run xq -o json health
uv run xq -o json doctor
uv run xq -o json recover stale-leases
```

## Database And Cleanup

```sh
uv run xq -o json db check
uv run xq -o json db vacuum
uv run xq -o json db cleanup-retention
uv run xq -o json db reset-workspace-instance --yes
uv run xq hooks install
uv run xq hooks status -o json
```

## JSON Output Rules

- list commands: `{ "items": [...] }`
- detail commands: `{ "item": { ... } }`
- successful mutations: `{ "ok": true, "item": { ... } }`
- structured logs go to `stderr`
- per-attempt operation logs go to `logs/jobs/<job-id>/attempt-0001.events.jsonl`
- TOON is the default stdout format

For more detail, see
[README.md](README.md) and [operations.md](operations.md).
