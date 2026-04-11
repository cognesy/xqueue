# Development

## Local Setup

Install dependencies and verify the CLI:

```sh
uv sync
uv run xq --help
uv run pytest
```

The project is packaged with `uv`, and the console script entrypoint is
`xq = apps.cli.main:main`.

## Repository Layout

The enforced layout is:

- `apps/`: runnable shells only
- `libs/`: importable code only
- `resources/`: Alembic, static config assets, schemas
- `tests/<module>/{unit,feature,integration,regression}/`
- `instance/`: local mutable runtime state for repo-local runs
- `docs/{dev,spec,user}/`

The main dependency rule is:

`apps -> actions -> services`

App shells must not call services directly.

## Layer Responsibilities

Apps:

- parse CLI input
- construct an `Output` object and choose output format through contracts
- construct actions with explicit dependencies
- translate errors to exit codes

Actions:

- represent use cases
- receive dependencies through the constructor
- orchestrate domain rules and service calls
- are the main subject of application logging

Services:

- wrap integrations such as SQLite, subprocesses, filesystem access, and
  service-manager APIs
- stay context-agnostic
- do not know whether the caller is CLI, worker, or controller code

## Logging

Application logging uses `structlog`.

Action entrypoints should use the shared
[logging.py](/Users/ddebowczyk/projects/xqueue/libs/actions/logging.py)
decorator instead of open-coded per-action logging. That keeps start, success,
failure, duration, and structured context consistent across the application.

Current pattern:

- `libs/services/logging.py` configures `structlog`
- `libs/actions/logging.py` provides `@log_action(...)`
- CLI shells call `configure_logging()` once at process startup
- action logs go to `stderr` as structured JSON
- defaults live in `resources/logging/default.yaml`
- `XQUEUE_LOG_LEVEL` and `XQUEUE_LOG_FORMAT` override the checked-in defaults

When adding a new action:

1. inject dependencies through `__init__`
2. keep `__call__` focused on one use case
3. add `@log_action(...)` with concise context and result metadata
4. avoid logging directly in CLI command functions unless it is shell-specific

## Runtime Paths

There are two important modes:

- installed usage: paths resolve through `platformdirs`
- local development: `--workspace-instance` resolves paths under `instance/`

Inspect the effective paths with:

```sh
uv run xq -o json config show --workspace-instance
```

Important local paths:

- `instance/xqueue.db`
- `instance/run/`
- `instance/logs/`
- `instance/config.yaml`

Job attempt logs live under `log_root/jobs/<job-id>/`.

Reset repo-local runtime state used by `--workspace-instance`:

```sh
uv run xq -o json db reset-workspace-instance --yes
```

This removes owned repo-local DB, runtime, and log artifacts while preserving
`instance/config.yaml`.

## Database And Migrations

SQLite is the canonical mutable state store. The SQLAlchemy engine is configured
with:

- WAL mode
- explicit sessions and transactions
- `busy_timeout`
- foreign keys enabled

Alembic assets live under `resources/alembic/`, with repository config in
[alembic.ini](/Users/ddebowczyk/projects/xqueue/alembic.ini).

Upgrade the local database:

```sh
uv run alembic upgrade head
```

Point migrations at another database path:

```sh
XQUEUE_DB_PATH=/tmp/xqueue.db uv run alembic upgrade head
```

When changing persistence:

1. update ORM models under `libs/infra/`
2. create an Alembic revision under `resources/alembic/versions/`
3. verify upgrade behavior
4. keep Pydantic domain models separate from ORM models

## Test Workflow

Run the full suite:

```sh
uv run pytest tests -x
```

Useful narrower targets:

```sh
uv run pytest tests/cli -x
uv run pytest tests/actions -x
uv run pytest tests/infra/integration/test_alembic_schema.py -x
```

Tests are grouped by module and level so behavior stays visible:

- `unit`: local logic
- `feature`: behavior-focused slice tests
- `integration`: boundary and persistence tests
- `regression`: locked-in behavior and bug prevention

Prioritize tests around:

- TOON output contracts
- JSON output contracts
- field filtering and format propagation
- state transitions
- concurrent claims
- cancellation and timeout behavior
- stale lease recovery
- controller supervision
- platform service artifact rendering

## Documentation Boundaries

Keep the documentation split clean:

- `docs/spec/`: product intent and constraints
- `docs/user/`: operator workflows and command examples
- `docs/dev/`: contributor architecture and engineering workflow

If implementation diverges from the spec, update code or docs so operator guides
describe shipped behavior accurately, then capture any remaining gap explicitly.
