---
name: admin-xqueue
description: >-
  Operate xqueue as an administrator. Use this skill when you need to diagnose
  queue or worker issues, inspect health, recover stale leases, maintain the
  SQLite store, manage controller mode, or perform operator/admin actions
  beyond routine day-to-day job usage.
---

# Admin XQueue

Use this skill for `xqueue` troubleshooting, operator interventions, and
maintenance.

This skill is for:

- health checks
- stale lease recovery
- queue and worker troubleshooting
- controller operations
- database maintenance
- retention cleanup
- repo-local reset in development

This is not the normal usage skill. For routine enqueue/list/show/worker use,
see `resources/skills/use-xqueue/SKILL.md`.

## Admin Mental Model

`xqueue` is a local durable queue with:

- SQLite as canonical mutable state
- at-least-once semantics
- attempt logs in files
- workers using leases and heartbeats
- a direct worker mode and an optional controller mode

Admin implications:

- a healthy DB and healthy runtime paths matter
- stale lease recovery is part of normal reliability behavior
- worker heartbeats and lease timestamps are operational signals
- logs and DB rows must be interpreted together

## First Response Workflow

When something looks wrong, do this first:

1. Check effective config and paths:

```sh
uv run xq config show --output json
```

2. Check high-level health:

```sh
uv run xq health --output json
```

3. Run detailed diagnostics:

```sh
uv run xq doctor --output json
```

4. Inspect current jobs, queues, workers, and controller state:

```sh
uv run xq jobs list --output json
uv run xq queues stats --output json
uv run xq workers list --output json
uv run xq controller status --output json
```

5. Inspect one suspect job in detail:

```sh
uv run xq jobs show <job-id> --output json
uv run xq jobs tail <job-id> --output json
```

## Health And Diagnosis

Use:

```sh
uv run xq health --output json
uv run xq doctor --output json
```

Interpretation:

- paused queues are warnings, not necessarily failures
- stale leases usually mean a crashed or wedged worker path
- stale workers mean heartbeat problems or dead worker processes

Do not guess from one signal alone. Check:

- worker list
- job detail
- stale lease output
- attempt logs

## Stale Lease Recovery

Recover stale work with:

```sh
uv run xq recover stale-leases --output json
```

Use this when:

- a worker died after claiming a job
- jobs are stuck `running` with expired leases
- health/doctor reports stale leases

Expected outcome:

- jobs are requeued or failed based on retry policy
- recovery is recorded in job history

After recovery, inspect:

```sh
uv run xq jobs show <job-id> --output json
```

## Queue And Worker Administration

Queue controls:

```sh
uv run xq queues list --output json
uv run xq queues stats --output json
uv run xq queues pause <queue>
uv run xq queues resume <queue>
```

Worker controls:

```sh
uv run xq workers list --output json
uv run xq workers pause <worker-id>
uv run xq workers resume <worker-id>
uv run xq workers drain <worker-id>
uv run xq workers stop <worker-id>
```

Use them like this:

- `pause` to stop new claims temporarily
- `drain` to let current work finish without taking more
- `stop` when you need the worker to exit

Prefer `drain` before `stop` when possible.

## Controller Operations

Direct controller mode:

```sh
uv run xq controller run --controller-id default
uv run xq controller status --controller-id default --output json
uv run xq controller pause-intake --controller-id default
uv run xq controller resume-intake --controller-id default
uv run xq controller drain --controller-id default
uv run xq controller restart --controller-id default
uv run xq controller stop --controller-id default
```

Semantics:

- `pause-intake` stops controller-managed workers from taking new work
- `resume-intake` returns intake to active
- `drain` lets current work finish and then exits workers
- `restart` reloads config in direct mode before recreating worker pools
- `stop` requests shutdown

Important distinction:

- `queues pause` is per queue
- `controller pause-intake` is controller-wide for its pools

Managed mode:

macOS:

```sh
uv run xq controller install --platform launchd
uv run xq controller start --platform launchd
uv run xq controller status --platform launchd --output json
uv run xq controller restart --platform launchd
uv run xq controller stop --platform launchd
uv run xq controller uninstall --platform launchd
```

Linux:

```sh
uv run xq controller install --platform systemd
uv run xq controller start --platform systemd
uv run xq controller status --platform systemd --output json
uv run xq controller restart --platform systemd
uv run xq controller stop --platform systemd
uv run xq controller uninstall --platform systemd
```

Only touch service definitions owned by `xqueue`.

## Database Maintenance

Integrity and vacuum:

```sh
uv run xq db check --output json
uv run xq db vacuum --output json
```

Use `db check` when:

- startup or query paths fail unexpectedly
- health reports DB problems
- migrations or runtime state look inconsistent

Use `db vacuum` when:

- you intentionally want SQLite file compaction
- you have done cleanup and want to reclaim space

## Retention Cleanup

Explicit retention cleanup:

```sh
uv run xq db cleanup-retention \
  --older-than-hours 168 \
  --attempts \
  --events \
  --logs \
  --yes \
  --output json
```

This is operator-controlled. It does not run automatically.

Be careful:

- removing attempts reduces detailed history
- removing logs removes per-attempt output files

Use this only when you intend to prune old history.

## Repo-Local Reset

For development in this repo only:

```sh
uv run xq db reset-workspace-instance --yes --output json
```

This removes owned repo-local runtime artifacts while preserving
`instance/config.yaml`.

Do not use this casually on a system with data you want to keep.

## Troubleshooting Patterns

### Job stuck running

1. `xq jobs show <job-id> --output json`
2. `xq workers list --output json`
3. `xq health --output json`
4. if lease is stale: `xq recover stale-leases --output json`

### Worker looks alive but nothing is moving

1. check queue pause state: `xq queues stats --output json`
2. check worker state: `xq workers list --output json`
3. check controller state: `xq controller status --output json`
4. check job availability windows with `jobs list`

### Controller-managed pool is not taking new work

1. `xq controller status --output json`
2. check whether controller is `paused`, `draining`, or `stopped`
3. check whether queues are paused
4. resume intake or resume queues as appropriate

### Suspected DB problem

1. `xq db check --output json`
2. `xq doctor --output json`
3. inspect resolved DB path with `xq config show --output json`

## Output Discipline For Agents

Prefer JSON for automation:

- read `stdout` as the API payload
- read `stderr` as structured `structlog` output

Do not scrape text output when JSON exists.

## Things Not To Do

- Do not assume exactly-once execution.
- Do not delete running jobs.
- Do not use retention cleanup or workspace reset without intent.
- Do not confuse queue pause with controller pause-intake.
- Do not mutate unmanaged platform service definitions.
- Do not treat stale lease recovery as data loss; it is part of the reliability model.

## Repo-Local Development Note

In this repository, `--workspace-instance` resolves runtime data under:

- `instance/xqueue.db`
- `instance/run/`
- `instance/logs/`
- `instance/config.yaml`

Use it when you want deterministic local admin operations inside the repo.

## References

- `docs/user/README.md`
- `docs/user/operations.md`
- `docs/user/CHEATSHEET.md`
- `docs/dev/development.md`
