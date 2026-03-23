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
uv run xq config show --workspace-instance --output json
```

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
uv run xq jobs show <job-id> --workspace-instance --output json
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

For day-to-day operation, see
[operations.md](/Users/ddebowczyk/projects/xqueue/docs/user/operations.md).
