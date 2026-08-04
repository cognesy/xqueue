# xqueue

`xqueue` (`xq`) is a CLI-first, single-machine durable work queue for running
shell commands.

## Problem

Local automation often needs durability, retries, cancellation, worker
concurrency, and inspectable logs without adopting a distributed broker or
turning every task into an application-specific callable. `xqueue` keeps the
unit of work simple: one shell command plus execution metadata.

It is designed to complement tools such as `xcron`, which can detect periodic
work and enqueue command jobs, while `xq` workers own execution and state.

## Example Usage

```sh
uv run xq workspace init
uv run xq enqueue --queue default -- /bin/sh -lc 'echo hello'
uv run xq jobs list
uv run xq worker run --queue default --execute-claimed
uv run xq -o json jobs show <job-id>
uv run xq jobs tail <job-id> --stream stdout
```

Operational commands include:

```sh
uv run xq queues stats
uv run xq workers list
uv run xq recover stale-leases
uv run xq doctor
```

## How It Works

Jobs are stored durably in SQLite and move through explicit states such as
`queued`, `running`, `succeeded`, `failed`, `retry_scheduled`, and `canceled`.
Workers claim jobs transactionally, execute subprocesses in process groups,
heartbeat leases, capture stdout and stderr to log files, and record each
attempt separately.

The system is at-least-once, not exactly-once. If a worker crashes after
claiming a job, stale lease recovery can make the job runnable again.

## Documentation

- Operator guides: [docs/user/README.md](docs/user/README.md)
- Developer workflow: [docs/dev/README.md](docs/dev/README.md)
- Product specification: [SPEC.md](SPEC.md)

## Development

```sh
uv sync
uv run xq --help
uv run xq
uv run pytest
```

## AXI Output

`xq` now defaults to TOON for agent-facing stdout. Use `-o` / `--output` to
switch formats:

```sh
uv run xq jobs list
uv run xq -o json queues list
uv run xq --fields id,state jobs list
```

Available formats:

- `toon` (default)
- `json`
- `jsonl`
- `text`
- `tmux`

See [SPEC.md](SPEC.md) for the product specification.

## Python SDK

The public library starts at one lifecycle-safe root, `Xqueue`, with cached
capability facets. Use it as a context manager so its SQLite resources are
disposed deterministically:

```python
from pathlib import Path

from xqueue import Xqueue

with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as xq:
    job = xq.jobs.enqueue(queue="default", command="echo hello from the SDK")
    current = xq.jobs.show(job.id)
```

`enqueue` also accepts the validated model directly, for callers that build it
themselves:

```python
from xqueue.jobs.models import EnqueueJobInput

job = xq.jobs.enqueue(EnqueueJobInput(queue="default", command="echo hi"))
```

The public facets are `jobs`, `queues`, `workers`, `controller`, `maintenance`,
and `workspace`. They return typed domain values; CLI envelopes and rendering
remain owned by `apps/cli/`.

`open` takes the same configuration inputs the CLI exposes as `--config`,
`--env`, and `--set` -- a file that replaces the shipped defaults, an overlay
name, and dotted-path overrides:

```python
with Xqueue.open(
    workspace_root=Path.cwd(),
    env_name="staging",
    overrides={"worker.retry_delay_seconds": "30"},
) as xq:
    settings = xq.workspace.config()
```

Anything that will not compose raises `ConfigurationError`.

Embedders install `xqueue` and get the SDK alone. Operators install
`xqueue[cli]`, which adds Typer, Rich, and python-toon for the `xq` command.

## Tech Stack

- Python 3.11+
- Typer for the CLI (the `cli` extra)
- Rich for human-readable text output (the `cli` extra)
- Pydantic for domain and response models
- SQLAlchemy and Alembic with SQLite for durable state
- `.xqueue/` in a project, or `~/.xqueue/` outside one (`XQUEUE_HOME` to override),
  for config, state, runtime, and log paths
- `xcfg` for layered configuration, behind one adapter
- PyYAML for the logging profile and controller pool files
- structlog for application logs
- python-toon for compact agent-facing output
- pytest for tests

The implementation keeps Typer shells and all rendering in `apps/cli/`.
`libs/` is organized by public capabilities (`jobs`, `queues`, `workers`,
`controller`, `maintenance`, and `workspace`), with shared invariants in
`core/`, runtime composition in `runtime/`, and SQLite sealed behind
`adapters/sqlite/`. Alembic migrations and packaged static assets live in
`resources/`.
