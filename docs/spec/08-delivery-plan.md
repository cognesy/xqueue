# Delivery Plan

This chapter is derived from the root `SPEC.md`.
`SPEC.md` remains the canonical source of truth.

## Implementation Direction

The implementation should follow the same general philosophy as `xcron`:

- thin CLI shells in `apps/`
- reusable logic in `libs/`
- explicit schemas and resources in `resources/`
- docs in `docs/`

Suggested initial layout:

```text
apps/
  cli/
libs/
  actions/
  domain/
  infra/
  services/
resources/
  schemas/
docs/
```

The Python project tooling should be designed around `uv` from the start:

- `uv sync`
- `uv run xq ...`
- `uv run pytest`
- `uv run alembic upgrade head`

The project should not assume ad hoc `pip` workflows as the primary path.

Schema evolution should use Alembic from the beginning even if the initial
schema is small.

## Testing Direction

The project should include tests for:

- CLI behavior
- JSON output shapes
- state transitions
- concurrent worker claims
- timeout handling
- cancellation handling
- stale lease recovery
- SQLite persistence across process restarts
- pause, resume, and drain semantics
- queue purge behavior
- health and recovery commands
- exit-code behavior
- controller configuration loading
- platform service artifact rendering

`pytest-xdist` is optional and should only be introduced if the test suite grows
enough to justify parallel execution.

## Main Implementation Risks

The main risks are not the choice of CLI or ORM libraries.

The main risks are:

- atomic job claim logic
- worker crash recovery
- timeout and cancellation behavior for process groups
- keeping JSON output stable for agent automation

## First Milestone

The first useful milestone is:

1. enqueue command jobs into SQLite
2. run one worker process
3. support `queued`, `running`, `succeeded`, `failed`, `canceled`
4. support retries and timeouts
5. expose `jobs list/show/cancel/retry` via CLI
6. emit JSON for automation

If this milestone is solid, everything else can remain incremental.
