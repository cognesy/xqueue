# User Guide

`xqueue` (`xq`) is a local, durable queue for running shell commands on one
machine.

This section is for operators and automation authors. It covers the CLI that is
implemented in the repository today, not the broader long-term command surface
described in [SPEC.md](../../SPEC.md).

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

As a tool, the CLI needs its `cli` extra:

```sh
uv tool install "xqueue[cli]"
```

Installing bare `xqueue` gives you the Python SDK without Typer, Rich, or
python-toon. The `xq` script is still installed, and says so:

```text
$ xq --help
xq requires the cli extra: pip install "xqueue[cli]"
```

The console script entrypoint is `xq`. Run `xq workspace init` once to create
a `.xqueue/` directory here, and every command in this guide will find it by
walking up from the working directory. Without one, they use the machine-wide
instance at `XQUEUE_HOME`, or `~/.xqueue/`.

To inspect the resolved paths:

```sh
uv run xq -o json config show
```

## Output Modes

`xq` defaults to TOON on stdout so agents get compact structured output without
extra flags.

Use `-o` / `--output` to override the format:

```sh
uv run xq jobs list
uv run xq -o json jobs show <job-id>
uv run xq -o text doctor
uv run xq --fields id,state jobs list
```

Available formats:

- `toon` (default)
- `json`
- `jsonl`
- `text`
- `tmux`

`--fields` narrows TOON output and can also narrow JSON when explicitly
requested. Application logs remain on `stderr`.

## Repository Quality Workflow

The repository uses `xqa` for workflow readiness and catalog verification. Its
current mechanism catalog is data-only, so developers run native tools directly.

Use:

- `xqa doctor --root . --format json` for shared workflow readiness
- `xqa mechanism verify --format json` for catalog integrity
- `uvx ruff check apps libs tests scripts` for lint and import hygiene
- `uv run python scripts/check_architecture.py` for architecture boundaries
- `uv run pytest` for behavior

Boundary:

- `xq doctor` / `xq health` remain the source of truth for `xqueue` runtime and
  operational health
- `xqa doctor` is only about the repo's shared `xqa` setup

## Quick Start

Enqueue a shell command:

```sh
uv run xq enqueue \
  --queue default \
  -- /bin/sh -lc 'echo hello from xqueue'
```

List jobs:

```sh
uv run xq jobs list
```

Run one worker poll and execute the claimed job:

```sh
uv run xq worker run \
  --queue default \
  --execute-claimed
```

Inspect the result:

```sh
uv run xq -o json jobs show <job-id>
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
- `xq controller pools list|ensure|remove`
- `xq controller run|status|install|uninstall|start|drain|restart|stop`
- `xq config show`
- `xq health`
- `xq doctor`
- `xq recover stale-leases`
- `xq db check|vacuum`
- `xq hooks install|status`

For day-to-day operation, see
[operations.md](operations.md).
