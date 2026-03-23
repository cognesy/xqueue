# XQueue Cheat Sheet

Quick operator reference for the currently shipped CLI.

Most examples below use `--workspace-instance` so repo-local state stays under
`instance/`.

## Basic Setup

```sh
uv sync
uv run xq --help
uv run xq config show --workspace-instance --output json
```

## Enqueue Jobs

```sh
uv run xq enqueue \
  --workspace-instance \
  --queue agent \
  -- /bin/sh -lc 'echo hello from xqueue'
```

With more execution options:

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

## Inspect Jobs

```sh
uv run xq jobs list --workspace-instance
uv run xq jobs list --workspace-instance --queue agent --state queued --output json
uv run xq jobs show <job-id> --workspace-instance --output json
uv run xq jobs tail <job-id> --workspace-instance --output json
uv run xq jobs tail <job-id> --workspace-instance --stream stdout --attempt-number 1 --lines 50
```

Filter and sort:

```sh
uv run xq jobs list \
  --workspace-instance \
  --queue agent \
  --created-after 2026-03-22T20:30:00Z \
  --available-before 2026-03-22T21:00:00Z \
  --sort available-desc \
  --output json
```

## Control Jobs

```sh
uv run xq jobs cancel <job-id> --workspace-instance
uv run xq jobs retry <job-id> --workspace-instance
uv run xq jobs delete <job-id> --workspace-instance --output json
uv run xq jobs purge --queue agent --workspace-instance
```

## Run Workers

One-shot claim:

```sh
uv run xq worker --workspace-instance --queue agent --output json
```

Execute claimed work:

```sh
uv run xq worker \
  --workspace-instance \
  --queue agent \
  --execute-claimed \
  --output json
```

Continuous direct worker with real concurrency:

```sh
uv run xq worker \
  --workspace-instance \
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
uv run xq queues list --workspace-instance --output json
uv run xq queues stats --workspace-instance --output json
uv run xq queues pause agent --workspace-instance
uv run xq queues resume agent --workspace-instance

uv run xq workers list --workspace-instance --output json
uv run xq workers pause <worker-id> --workspace-instance
uv run xq workers resume <worker-id> --workspace-instance
uv run xq workers drain <worker-id> --workspace-instance
uv run xq workers stop <worker-id> --workspace-instance
```

## Controller Mode

Run directly:

```sh
uv run xq controller run --workspace-instance --controller-id default
uv run xq controller status --workspace-instance --output json
```

Direct-mode control:

```sh
uv run xq controller pause-intake --workspace-instance
uv run xq controller resume-intake --workspace-instance
uv run xq controller drain --workspace-instance
uv run xq controller restart --workspace-instance
uv run xq controller stop --workspace-instance
```

Managed mode:

```sh
uv run xq controller install --workspace-instance --platform launchd
uv run xq controller start --workspace-instance --platform launchd
uv run xq controller status --workspace-instance --platform launchd --output json
uv run xq controller restart --workspace-instance --platform launchd
uv run xq controller stop --workspace-instance --platform launchd
uv run xq controller uninstall --workspace-instance --platform launchd
```

`pause-intake` is controller-wide for direct mode. `queues pause` is per queue.

## Health And Recovery

```sh
uv run xq health --workspace-instance --output json
uv run xq doctor --workspace-instance --output json
uv run xq recover stale-leases --workspace-instance --output json
```

## Database And Cleanup

```sh
uv run xq db check --workspace-instance --output json
uv run xq db vacuum --workspace-instance --output json
uv run xq db cleanup-retention --workspace-instance --output json
uv run xq db reset-workspace-instance --yes --output json
```

## JSON Output Rules

- list commands: `{ "items": [...] }`
- detail commands: `{ "item": { ... } }`
- successful mutations: `{ "ok": true, "item": { ... } }`
- structured logs go to `stderr`

For more detail, see
[README.md](/Users/ddebowczyk/projects/xqueue/docs/user/README.md) and
[operations.md](/Users/ddebowczyk/projects/xqueue/docs/user/operations.md).
