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
uv run xq enqueue --workspace-instance --queue default -- /bin/sh -lc 'echo hello'
uv run xq jobs list --workspace-instance
uv run xq worker run --workspace-instance --queue default --execute-claimed
uv run xq -o json jobs show <job-id> --workspace-instance
uv run xq jobs tail <job-id> --workspace-instance --stream stdout
```

Operational commands include:

```sh
uv run xq queues stats --workspace-instance
uv run xq workers list --workspace-instance
uv run xq recover stale-leases --workspace-instance
uv run xq doctor --workspace-instance
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

- Operator guides: [docs/user/README.md](/Users/ddebowczyk/projects/xqueue/docs/user/README.md)
- Developer workflow: [docs/dev/README.md](/Users/ddebowczyk/projects/xqueue/docs/dev/README.md)
- Product specification: [SPEC.md](/Users/ddebowczyk/projects/xqueue/SPEC.md)

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

See [SPEC.md](/Users/ddebowczyk/projects/xqueue/SPEC.md) for the product
specification and [xqueue-spec-implementation.md](/Users/ddebowczyk/projects/xqueue/docs/dev/plans/xqueue-spec-implementation.md)
for the current implementation plan.

## Tech Stack

- Python 3.11+
- Typer for the CLI
- Rich for human-readable text output
- Pydantic for domain and response models
- SQLAlchemy and Alembic with SQLite for durable state
- platformdirs for config, state, runtime, and log paths
- PyYAML for static configuration
- structlog for application logs
- python-toon for compact agent-facing output
- pytest for tests

The implementation keeps Typer command shells in `apps/cli/`, use-case actions
in `libs/actions/`, domain models in `libs/domain/`, database models and session
setup in `libs/infra/`, execution, worker, controller, and platform integrations
in `libs/services/`, and Alembic migrations plus packaged skills in
`resources/`.
