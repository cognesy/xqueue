# Development

## Local Setup

Install dependencies and verify the CLI:

```sh
uv sync
uv run xq --help
uv run pytest
```

The project is packaged with `uv`, and the console script entrypoint is
`xq = xqueue_cli.entry:main`. `entry.py` imports nothing outside the standard
library, so `xq` installed without the `cli` extra exits 2 with a hint instead
of a traceback from inside Typer's import graph. The Typer application itself
stays in `xqueue_cli.main`.

Typer, Rich, and python-toon are the `cli` extra, not base dependencies: every
import of them lives under `apps/cli/`, so embedding `Xqueue` should not
install them. The dev group asks for `xqueue[cli]`, so `uv sync --group dev`
still gives you a working `xq`.

Do not import `click`. Typer vendored it in 0.27, and the floor here is 0.16, so
an installed `xqueue[cli]` may have no importable `click` at all -- and where
one exists it keeps a *different* context stack from the one Typer pushes onto,
which fails silently rather than loudly. Anything the root callback needs to
share with a command goes through `xqueue_cli.client`. Only the packaging tests
see this: they install the wheel into an isolated environment, which resolves a
newer Typer than the pinned dev one.

## Repository Layout

The enforced layout is:

- `apps/`: runnable shells only
- `libs/`: importable code only
- `resources/`: Alembic, static config assets, schemas
- `tests/<capability-or-channel>/{unit,feature,integration,regression}/`,
  plus the cross-cutting `tests/{architecture,packaging,sdk}/`
- `.xqueue/`: this repository's workspace -- marker, config, database,
  run and log roots
- `docs/{dev,spec,user}/`

The main dependency rule is:

`apps/cli -> capability APIs -> capability actions/ports -> adapters`

Adapters are the only place the engine, the session factory, and the ORM models
live. Capability persistence modules build SQLAlchemy queries against a session
the action opens; see the persistence boundary in `docs/dev/architecture.md`.

The public Python entry point is `xqueue.Xqueue`. CLI commands use the same
capability facets instead of constructing a parallel application graph.

## Layer Responsibilities

CLI apps:

- parse CLI input
- call a capability through the shared `Xqueue` runtime
- construct stable response envelopes through CLI-owned contracts
- choose output format through the CLI-owned `Output` surface
- translate errors to exit codes

Capabilities:

- group public models, ports, actions, and a typed facet by operator concept
- expose typed values without CLI envelopes or presentation dependencies
- receive concrete adapters through one runtime composition root
- own their state transitions and process/platform mechanics

Shared internals:

- `libs/core/` contains only genuinely cross-capability invariants
- `libs/runtime/` owns configuration, lifecycle, logging, and composition
- `libs/adapters/sqlite/` seals SQLAlchemy and SQLite setup
- `resources/` contains Alembic and other packaged static assets

## Logging

Application logging uses `structlog`.

Capability actions should use the shared
[action_logging.py](../../libs/runtime/action_logging.py) decorator instead of
open-coded per-action logging. That keeps start, success, failure, duration, and
structured context consistent across the application.

Current pattern:

- `libs/runtime/logging.py` configures `structlog`
- `libs/runtime/action_logging.py` provides `@log_action(...)`
- CLI shells call `configure_logging()` once at process startup
- action logs go to `stderr` as structured JSON
- defaults live in `resources/logging/default.yaml`
- `XQUEUE_LOG_LEVEL` and `XQUEUE_LOG_FORMAT` override the checked-in defaults

When adding a new action:

1. keep it inside the capability that owns the behavior
2. inject ports or collaborators through `__init__`
3. keep `__call__` focused on one use case
4. add `@log_action(...)` with concise context and result metadata
5. avoid logging directly in CLI command functions unless it is shell-specific

## Runtime Paths

There are two important modes:

- inside a workspace: every command walks up from the working directory and
  uses the nearest `.xqueue/` holding a valid marker
- outside one: paths resolve under `~/.xqueue/` (`XQUEUE_HOME` to override)

Create this repository's workspace once, then inspect the effective paths:

```sh
uv run xq workspace init
uv run xq -o json config show
```

Important local paths:

- `.xqueue/marker.toml`
- `.xqueue/config.yaml`
- `.xqueue/xqueue.db`
- `.xqueue/run/`
- `.xqueue/logs/`

Job attempt logs live under `log_root/jobs/<job-id>/`.

Reset repo-local runtime state:

```sh
uv run xq -o json db reset-workspace-instance --yes
```

This removes owned repo-local DB, runtime, and log artifacts while preserving
`.xqueue/config.yaml`.

## Configuration

`libs/workspace/loader.py` is the only module that may import the configuration
library, and the only place layers are composed. Everything else passes a
`ConfigInputs` in and reads an `EffectiveConfig` out. The layer order and what
each layer may contain is in
[`architecture.md`](architecture.md#configuration-boundary).

Both channels take the same three inputs:

```sh
uv run xq --config ./other.yaml --env staging \
          --set worker.retry_delay_seconds=30 -o json config show
```

```python
Xqueue.open(config_path=..., env_name="staging",
            overrides={"worker.retry_delay_seconds": "30"})
```

Defaults are stated in `resources/config/config.default.yaml`, not only in the
model, so `xq config show` and the file agree. The four path fields are
deliberately absent from it: unset, they derive from the resolved workspace.

An environment variable is a settings override only if it carries the nested
delimiter, as in `XQUEUE_WORKER__RETRY_DELAY_SECONDS`. The flat `XQUEUE_HOME`,
`XQUEUE_ROOT`, and `XQUEUE_DB_PATH` are resolution inputs read before any of
this and are invisible to the environment layer. `XQUEUE_CONFIG_PATH` and
`XQUEUE_ENV` name a file and an overlay respectively; they are not settings.

Anything that will not compose raises `ConfigurationError`, which the CLI
renders as an error envelope with exit code 2. That happens while a command is
opening its client, before `run_action` exists to catch it, so a group-level
handler in `apps/cli/errors.py` renders it -- which is why `-o json` has to be
given at the root to see one as JSON.

## Database And Migrations

SQLite is the canonical mutable state store. The SQLAlchemy engine is configured
with:

- WAL mode
- explicit sessions and transactions
- `busy_timeout`
- foreign keys enabled

Alembic assets live under `resources/alembic/`, with repository config in
[alembic.ini](../../alembic.ini).

Upgrade the local database:

```sh
uv run alembic upgrade head
```

Point migrations at another database path:

```sh
XQUEUE_DB_PATH=/tmp/xqueue.db uv run alembic upgrade head
```

When changing persistence:

1. update ORM models under `libs/adapters/sqlite/`
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
uv run pytest tests/jobs tests/queues tests/workers -x
uv run pytest tests/adapters/integration/test_alembic_schema.py -x
uv run pytest tests/sdk tests/packaging tests/architecture -x
```

## Architecture And Quality Gates

Run all structural checks before handing off a refactor:

```sh
uvx ruff check apps libs tests scripts
uvx ruff format --check apps libs tests scripts
uv run lint-imports
uv run mypy
uv run python scripts/check_python_boundaries.py
uv run python scripts/check_architecture.py
uv run pytest
```

This is the canonical gate list; `AGENTS.md` points here rather than repeating
it. Ad-hoc tools run through `uvx` and declared dependencies through `uv run`,
so a clean checkout needs nothing but `uv sync --group dev`.
`scripts/check_architecture.py` runs Semgrep itself through `uvx` and owns the
ratchet allowances, so Semgrep is never invoked directly.

The shared `xqa` workflow checks are separate, and need the sibling repository
checked out at `../xqa`:

```sh
uv run --project ../xqa --all-packages xqa doctor --root . --format json
uv run --project ../xqa --all-packages xqa mechanism verify --format json
```

The checks protect both dependency direction and physical absence of the former
global technical-layer packages.

Build wheels and sdists from a clean tree:

```sh
rm -rf build dist
uv build
```

setuptools reuses `build/lib` between builds, so a module deleted from `libs/`
can survive there and be packaged into a wheel. That has happened twice in this
repository. `tests/packaging/integration/test_installed_artifact.py` removes
`build/` around its own build for the same reason, and still rejects any
`xqueue/{actions,domain,infra,services}/` entry in the wheel as the backstop.

`mypy` checks the shipped package names, not the source directory names. The
wheel remaps `libs` to `xqueue` and `apps/cli` to `xqueue_cli`, and the editable
install resolves them through an import finder mypy cannot follow, so
`.typecheck/` holds one symlink per shipped package and `mypy_path` points at
it. Nothing else reads that directory.

Tests are grouped by the capability or channel they exercise, then by level, so
behavior stays visible:

- `tests/{jobs,queues,workers,controller,maintenance,workspace,runtime,adapters}/`
  mirror the shipped `xqueue.*` packages
- `tests/cli/` covers the `xqueue_cli` channel, including its renderers and
  response envelopes
- `tests/{architecture,packaging,sdk}/` are cross-cutting suites and stay flat

Levels inside a capability or channel directory:

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
