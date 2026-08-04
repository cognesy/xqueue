# Target Architecture

## Package Shape

Keep one distribution. Preserve `apps/cli` as the Typer channel and map the
existing `libs/` physical directory to the public `xqueue` Python package.

```text
apps/
  cli/                              # xqueue_cli; Typer and presentation only
    commands/
    contracts.py                    # CLI output contracts and field metadata
    output.py                       # text/json/jsonl/toon/tmux projection
    renderers/
libs/                               # import package: xqueue
  __init__.py                       # small public SDK export surface
  py.typed
  sdk/
    client.py                       # Xqueue lifecycle/composition facade
    errors.py                       # stable embedding errors
  runtime/
    composition.py                  # the only concrete assembly policy
    lifecycle.py                    # ownership and closed-state guard
  capabilities/
    jobs/
      models.py
      ports.py
      actions/
      api.py
    queues/
      models.py
      ports.py
      actions/
      api.py
    workers/
      models.py
      ports.py
      actions/
      runtime.py
      api.py
    controller/
      models.py
      ports.py
      actions/
      api.py
    maintenance/
      models.py
      ports.py
      actions/
      api.py
    workspace/
      models.py
      actions/
      api.py
  adapters/
    sqlite/
      database.py
      models.py
      unit_of_work.py
      jobs.py
      queues.py
      workers.py
      recovery.py
      maintenance.py
    process/
      execution.py
      controller.py
    filesystem/
      job_logs.py
      metrics.py
      operation_logs.py
      retention.py
    platform/
      launchd.py
      systemd.py
    configuration/
      loader.py
    observability/
      logging.py
resources/
tests/
  architecture/
  contract/
  feature/
  integration/
  unit/
```

This is a target map, not a command to create empty directories. A package is
introduced only when its stone moves real behavior and deletes the replaced
path. Small capabilities may keep multiple logical roles in one module until a
split hides an observed decision.

## Dependency Direction

```text
xqueue_cli -----> xqueue SDK / public capability types
                       |
                       v
                capability APIs
                       |
                       v
                typed actions and ports <----- runtime composition
                       |                              |
                       v                              v
                 capability models             concrete adapters
                                                      |
                                                      v
                                               SQLite / OS / files
```

The permitted capability dependency graph is:

```text
jobs <----- queues
  ^
  +------- workers <----- controller
  ^           ^               ^
  +-----------+---------------+----- maintenance

workspace/configuration -----> runtime composition only
```

`maintenance` is a higher-level operator capability for health, doctor,
recovery, database maintenance, retention, and metrics. It may consume public
ports and result types from the runtime capabilities. Lower capabilities never
import it.

## Use-Case and Transaction Boundary

One action represents one operator-visible use case. It accepts one strict input
model, returns one strict result model, raises stable typed errors, and owns the
read or write unit-of-work boundary.

For SQLite-backed actions, use consumer-owned unit-of-work protocols. The
protocol exists to stop SQLAlchemy sessions and ORM objects from leaking, not to
promise an unsupported database backend.

```python
class EnqueueUnitOfWork(Protocol):
    jobs: EnqueueJobStore

    def __enter__(self) -> EnqueueUnitOfWork: ...
    def __exit__(self, *exc_info: object) -> None: ...
    def commit(self) -> None: ...


class EnqueueJob:
    def __init__(self, uow: Callable[[], EnqueueUnitOfWork], ...) -> None: ...

    def execute(self, request: EnqueueJobInput) -> JobDetail:
        with self._uow() as tx:
            result = tx.jobs.enqueue(...)
            tx.commit()
        return result
```

Protocols should be as narrow as the consuming action family. Avoid a catch-all
repository manager or a general dependency container passed into actions.

## SDK Contract

The root facade owns validated settings, runtime resources, and one instance of
each capability facade:

> Superseded on 2026-08-04 by Stone 4 of the house-template-alignment plan:
> `open` also takes `env_name` and `overrides`, and `use_workspace_instance`
> now pins `.xqueue/` rather than the former `instance/`. See that plan's
> `STONE-LOG.md`. Left in place as the record of what was designed here.

```python
with Xqueue.open(
    workspace_root=Path.cwd(),
    config_path=None,
    use_workspace_instance=False,
) as xq:
    xq.jobs
    xq.queues
    xq.workers
    xq.controller
    xq.maintenance
    xq.workspace
```

Rules:

- `open()` resolves workspace and configuration once and then composes the
  runtime;
- resources created by the client are owned and closed by it;
- `close()` is idempotent;
- use after close raises `ClientClosedError`;
- no long-lived SQLAlchemy `Session` is stored on the client;
- each action receives a fresh unit of work;
- capability properties return stable, cached facet objects;
- SDK methods return capability models directly;
- SDK errors never contain Typer exit codes or rendered messages; and
- importing `xqueue` must not import Typer, Rich, or platform-specific service
  adapters eagerly.

Do not expose arbitrary dependency injection in the initial public API. The
runtime may have an internal/test construction seam, but SQLite is a fixed
product choice and public replaceability would be a false promise.

## CLI Contract

Each command performs four channel operations:

1. parse and validate channel syntax;
2. open the client with root/config choices from CLI context;
3. call one capability use case, with bounded channel-only fan-out when a CLI
   command genuinely represents multiple calls; and
4. project the typed result to the existing command contract and render it.

The CLI may import:

- `xqueue` public SDK objects;
- public capability input/result models and errors; and
- other `xqueue_cli` presentation helpers.

It may not import runtime composition internals, adapters, SQLAlchemy,
capability private modules, or global service modules. `home` becomes a typed
maintenance/read-model action rather than an exception to the rule.

CLI list/show/mutation envelopes remain stable boundary projections:

```json
{"items": []}
{"item": {}}
{"ok": true, "item": {}}
```

The SDK does not return these envelopes.

## Capability Ownership

### Jobs

Own enqueue, list, show, cancel, retry, delete, tail, pane, prune, purge, job
state, attempt history, event views, and job persistence ports.

### Queues

Own queue state, list, stats, pause, resume, and queue-level purge policy. Queue
statistics may consume job-state contracts but must not import SQLite models.

### Workers

Own worker registration/state, atomic claiming, heartbeats, attempt execution,
retry/timeout/cancel outcomes, polling, and direct worker loops. Split the large
current worker action module along these hidden decisions, not merely by file
size. Process-group mechanics are a consumed adapter.

### Controller

Own pool configuration, worker-process supervision, drain/stop/restart policy,
controller state, and managed-service lifecycle actions. Launchd and systemd
rendering/execution are adapters selected by composition.

### Maintenance

Own cross-capability health, doctor, stale-lease recovery, DB check/vacuum,
retention cleanup, metrics, and the compact home read model. It is allowed to
coordinate lower public ports; it owns no primary job transition that belongs
elsewhere.

### Workspace

Own resolved runtime paths, static configuration selection, workspace-instance
reset, resource lookup policy, CLI bootstrap information, and agent hook use
cases. Hook implementations remain filesystem/configuration adapters.

> Amended on 2026-08-04 by Stone 4 of the house-template-alignment plan:
> "static configuration selection" is now layered composition behind
> `workspace/loader.py`, the one module allowed to import `xcfg`. The
> ownership stated here did not change; what it composes did.

## Presentation and Observability

Move `axi_contracts.py`, `toon_renderer.py`, and `tmux_renderer.py` into the CLI
package. They are presentation mechanisms, not reusable business services.
Keep `structlog` configuration in an observability adapter composed at runtime;
actions emit structured facts through a narrow observer interface or action
decorator that does not configure global logging on every call.

## Mechanical Guardrails

Use complementary checks:

1. Import Linter for transitive package boundaries and sealed dependencies.
2. A small AST scanner for repository-specific rules such as CLI imports,
   private capability reach-around, and forbidden global technical packages.
3. Negative-fixture tests proving every architecture rule can fail.
4. Packaging tests for wheel/sdist imports, `py.typed`, resources, and eager
   dependency isolation.

Tach is not required initially. A second dependency graph is useful only if it
adds enforcement that Import Linter plus focused AST rules do not provide.
Avoid two configuration files that merely restate the same edges.
