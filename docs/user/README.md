# User Guide

`xqueue` (`xq`) is a local, durable queue for running shell commands on one
machine.

This section is for operators and automation authors. It covers the CLI that is
implemented in the repository today, not the broader long-term command surface
described in [SPEC.md](/Users/ddebowczyk/projects/xqueue/SPEC.md).

## Scope

`xqueue` is:

- a local-first queue backed by SQLite
- a CLI-first operator tool
- a small control plane for workers and an optional controller
- at-least-once, not exactly-once

`xqueue` is not:

- a scheduler
- a distributed broker
- a workflow or DAG engine
- a Python callable runner

## Install And Verify

From the repository:

```sh
uv sync
uv run xq --help
```

The console script entrypoint is `xq`. During local development, most examples
in this guide use `--workspace-instance` so state stays under the repository
`instance/` directory instead of platformdirs-managed user paths.

To inspect the resolved paths:

```sh
uv run xq -o json config show --workspace-instance
```

## Output Modes

`xq` defaults to TOON on stdout so agents get compact structured output without
extra flags.

Use `-o` / `--output` to override the format:

```sh
uv run xq jobs list --workspace-instance
uv run xq -o json jobs show <job-id> --workspace-instance
uv run xq -o text doctor --workspace-instance
uv run xq --fields id,state jobs list --workspace-instance
```

Available formats:

- `toon` (default)
- `json`
- `jsonl`
- `text`

`--fields` narrows TOON output and can also narrow JSON when explicitly
requested. Application logs remain on `stderr`.

## xqa Pilot Workflow

This repo now has a minimal `xqa` rollout that complements `xqueue`'s own
operator surfaces.

Use:

- `xqa doctor` for shared quality-workflow readiness
- `xqa profile run default` for the deterministic shared quality lane
- `xqa profile run style` for Ruff-only checks
- `xqa profile run architecture` for the Semgrep-backed architecture audit
- `xqa snap store` and `xqa progress` for before/current/remaining-work visibility

Boundary:

- `xq doctor` / `xq health` remain the source of truth for `xqueue` runtime and
  operational health
- `xqa doctor` is only about the repo's shared `xqa` setup

## Quick Start

Enqueue a shell command:

```sh
uv run xq enqueue \
  --workspace-instance \
  --queue default \
  -- /bin/sh -lc 'echo hello from xqueue'
```

List jobs:

```sh
uv run xq jobs list --workspace-instance
```

Run one worker poll and execute the claimed job:

```sh
uv run xq worker run \
  --workspace-instance \
  --queue default \
  --execute-claimed
```

Inspect the result:

```sh
uv run xq -o json jobs show <job-id> --workspace-instance
```

Install session hooks for Claude Code and Codex:

```sh
uv run xq hooks install
uv run xq hooks status -o json
```

## Command Surface

Current operator-facing commands:

- `xq enqueue`
- `xq jobs list|show|cancel|retry|delete|tail|purge`
- `xq queues list|stats|pause|resume`
- `xq worker run`
- `xq workers list|pause|resume|drain|stop`
- `xq controller run|status|install|uninstall|start|drain|restart|stop`
- `xq config show`
- `xq health`
- `xq doctor`
- `xq recover stale-leases`
- `xq db check|vacuum`
- `xq hooks install|status`

For day-to-day operation, see
[operations.md](/Users/ddebowczyk/projects/xqueue/docs/user/operations.md).
