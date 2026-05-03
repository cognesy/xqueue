---
name: use-xqueue
description: >-
  Operate xqueue as a normal user inside a larger local system. Use this skill
  when you need to enqueue command jobs, inspect job status, tail logs, run
  direct workers, or interact with xqueue as a routine workload tool rather
  than as an administrator.
---

# Use XQueue

Use `xqueue` (`xq`) as a local durable command queue on one machine.

This skill is for routine workload usage:

- enqueue work
- inspect jobs
- retry or cancel jobs
- tail attempt logs
- run direct workers as part of a broader automation flow

This is not the admin skill. For recovery, health, database maintenance,
controller installation, or deeper troubleshooting, use
`resources/skills/admin-xqueue/SKILL.md`.

## Mental Model

`xqueue` is:

- local-first
- SQLite-backed
- CLI-first
- command-oriented
- at-least-once

Implications:

- jobs must be safe under retry or duplicate execution
- mutable state lives in SQLite, not YAML
- stdout and stderr are stored in log files, not in DB blobs
- TOON is the default machine interface
- `-o json` is the stable envelope path
- structured app logs go to `stderr`

Stable JSON shapes:

- list commands: `{ "items": [...] }`
- detail commands: `{ "item": { ... } }`
- successful mutations: `{ "ok": true, "item": { ... } }`
- failures: `{ "ok": false, "error": { ... } }`

## When To Use This Skill

Use this skill when you need to:

- queue a shell command for later execution
- run a direct worker in-process
- check whether work succeeded or failed
- inspect attempts and log files
- retry, cancel, delete, or purge jobs

Do not use this skill for:

- stale lease recovery
- queue health diagnosis
- DB maintenance
- controller service-manager setup
- repo-local reset or cleanup

## Quick Workflow

1. Inspect resolved paths if needed:

```sh
uv run xq -o json config show
```

In repo-local development, prefer:

```sh
uv run xq -o json config show --workspace-instance
```

2. Enqueue work:

```sh
uv run xq enqueue \
  --queue agent \
  -- /bin/sh -lc 'echo hello from xqueue'
```

With common options:

```sh
uv run xq enqueue \
  --queue agent \
  --cwd /repo \
  --timeout-seconds 300 \
  --max-attempts 3 \
  --env AGENT_NAME=writer-1 \
  -- /bin/sh -lc 'python scripts/check_mailbox.py --agent writer-1'
```

3. Inspect jobs:

```sh
uv run xq jobs list --queue agent
uv run xq -o json jobs show <job-id>
uv run xq --fields id,state jobs list --queue agent
```

4. Run a direct worker when needed:

One-shot claim:

```sh
uv run xq -o json worker --queue agent
```

Execute claimed work:

```sh
uv run xq -o json worker --queue agent --execute-claimed
```

Long-running direct worker:

```sh
uv run xq worker \
  --queue agent \
  --continuous \
  --execute-claimed
```

Real direct-worker concurrency:

```sh
uv run xq worker \
  --queue agent \
  --concurrency 2 \
  --continuous \
  --execute-claimed
```

Important constraint:

- `--concurrency > 1` is only supported with `--continuous --execute-claimed`

## Job Inspection And Control

List jobs:

```sh
uv run xq -o json jobs list --queue agent --state queued
```

Filter and sort:

```sh
uv run xq jobs list \
  --queue agent \
  --created-after 2026-03-22T20:30:00Z \
  --available-before 2026-03-22T21:00:00Z \
  --sort available-desc \
  -o json
```

Show full detail:

```sh
uv run xq -o json jobs show <job-id>
```

Use the latest attempt paths from `jobs show`:

- `stdout_path` is raw command stdout
- `stderr_path` is raw command stderr
- `event_log_path` is JSONL job lifecycle telemetry

Tail attempt logs:

```sh
uv run xq -o json jobs tail <job-id>
uv run xq jobs tail <job-id> --stream stdout --attempt-number 1 --lines 50
```

For operational timing and correlation, read `event_log_path` directly. It
contains timestamped `job.claimed`, `job.started`, `job.finished`, and terminal
outcome events without embedding raw agent transcripts.

Control jobs:

```sh
uv run xq jobs cancel <job-id>
uv run xq jobs retry <job-id>
uv run xq -o json jobs delete <job-id>
uv run xq jobs purge --queue agent
```

Use these carefully:

- `cancel` for queued or running work you want stopped
- `retry` to requeue failed or canceled work without deleting history
- `delete` only for non-running cleanup
- `purge` only for queued or retry-scheduled jobs in a queue

## Queue And Worker Controls

Queue controls:

```sh
uv run xq queues list
uv run xq -o json queues stats
uv run xq queues pause agent
uv run xq queues resume agent
```

Worker controls:

```sh
uv run xq -o json workers list
uv run xq workers pause <worker-id>
uv run xq workers resume <worker-id>
uv run xq workers drain <worker-id>
uv run xq workers stop <worker-id>
```

Semantics:

- queue pause blocks new claims for one queue
- worker pause affects one persisted worker
- worker drain stops taking new work but lets current work finish

## Output Discipline For Agents

Prefer the default TOON output for quick agent inspection. Use `-o json` when
you need the stable JSON envelope, and `-o jsonl` when item streaming is a
better fit.

Treat:

- `stdout` as the structured API payload
- `stderr` as structured `structlog` output

Use `--fields` to narrow TOON or JSON payloads when you only need a subset of
fields.

## Common Mistakes To Avoid

- Do not assume exactly-once execution.
- Do not enqueue non-idempotent commands unless the caller can tolerate retry.
- Do not expect `--concurrency > 1` to work in one-shot direct worker mode.
- Do not use `jobs delete` on running jobs.
- Do not confuse queue pause with controller pause-intake.

## Repo-Local Development Note

When operating inside this repository, prefer `--workspace-instance` so all
state stays under `instance/`:

- `instance/xqueue.db`
- `instance/run/`
- `instance/logs/`
- `instance/config.yaml`

## References

- `docs/user/README.md`
- `docs/user/operations.md`
- `docs/user/CHEATSHEET.md`
