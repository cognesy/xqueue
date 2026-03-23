# Retrospective: xqueue-x6x

## Scope

Retrospective target:

- [xqueue-x6x](/Users/ddebowczyk/projects/xqueue/.beads) "Implement xqueue
  specification foundations and phased delivery"

Completion state at review time:

- `bd status --json`: 29 closed, 0 open, 0 in progress before retrospective
- root epic `xqueue-x6x`: closed
- child epics `xqueue-x6x.1` through `xqueue-x6x.7`: closed

This retrospective was performed after delivery was functionally complete and
after the final documentation and verification pass.

## What Was Delivered

The delivered implementation covers the planned phased baseline:

- repository structure under `apps/`, `libs/`, `resources/`, `tests/`,
  `instance/`, and `docs/`
- Typer CLI with stable text and JSON output contracts
- SQLite persistence with WAL mode, explicit sessions, and Alembic migrations
- durable enqueue and job inspection
- worker claim, execution, retries, cancellation, and timeout handling
- per-attempt stdout/stderr capture in files
- queue and worker controls
- stale lease recovery, health, doctor, and DB maintenance commands
- controller supervision plus `launchd` and `systemd --user` integration
- user and developer documentation
- behavioral and regression coverage

Verification evidence at closeout:

- `uv run pytest tests -q` passed with `70 passed`
- CLI walkthroughs were run for enqueue, jobs inspection, worker execution,
  queues/workers inspection, health, doctor, stale lease recovery, DB
  maintenance, and controller status

## Plan Versus Reality

The plan was mostly accurate.

What held up well:

- the phase split was correct
- core sequencing was correct: persistence before CLI, CLI before worker
  execution, worker correctness before controller/platform integration
- the highest-risk areas identified up front were the ones that did require the
  most care: claim correctness, process-group handling, JSON output stability

Where execution reality differed:

- controller/platform work flushed out late bugs that were not obvious from the
  plan, especially child-process output leaking into controller JSON output
- a flaky retry test had to be fixed after the real runtime behavior existed,
  which is a sign that timing-sensitive work benefits from stronger
  clock/availability modeling earlier
- some epics remained open even when all children were closed, so backlog
  closure required an explicit cleanup pass

No major mid-flight scope creep showed up in `bd`. The original breakdown was
good enough to carry the implementation through without replanning the tree.

## Implementation Findings

### Filed Follow-Up Work

Two concrete gaps were found during the retrospective and converted into new
`bd` tasks:

- `xqueue-06n`: implement missing `jobs delete` and `jobs tail` commands to
  complete the CLI contract
- `xqueue-191`: add a repo-local instance reset workflow for manual
  verification

### Remaining Gaps Against Repo Rules

1. The minimum CLI surface in
   [AGENTS.md](/Users/ddebowczyk/projects/xqueue/AGENTS.md) includes
   `jobs delete/tail`, but `uv run xq jobs --help` currently exposes only
   `list`, `show`, `cancel`, `retry`, and `purge`.

2. Repo-local manual verification leaves persistent state under `instance/`,
   which then affects later health output and makes operational checks noisy.
   This is not a product correctness bug, but it is a real workflow problem.

### Residual Risks

- Linux managed-controller lifecycle was covered by rendering and command-map
  tests, but real `systemctl --user` manual verification was not possible on
  the macOS verification machine.
- The repo-local `instance/` data now contains historical manual verification
  artifacts, so health output in this checkout reflects those artifacts unless
  the new reset workflow is added and used.

## Architecture Review

The delivered code is largely aligned with
[architecture.md](/Users/ddebowczyk/projects/xqueue/docs/dev/architecture.md)
and [AGENTS.md](/Users/ddebowczyk/projects/xqueue/AGENTS.md):

- app shells remain thin and invoke actions
- actions hold the use-case logic and are constructor-injected
- services encapsulate subprocesses, config, DB maintenance, recovery, and
  platform integration
- Pydantic domain models are separate from SQLAlchemy ORM models
- Rich is reserved for text output and JSON output bypasses Rich
- action-level logging uses `structlog`

No evidence was found of queue state leaking into YAML or stdout/stderr being
stored as DB blobs.

## What Worked Well

- The initial architecture constraints were strong enough to prevent expensive
  refactors later.
- Behavioral tests were added around the risky areas instead of only around
  individual helper functions.
- Manual verification was used where it mattered: process execution, timeout,
  cancellation, recovery, controller behavior, and service artifact rendering.
- The docs pass happened after the runtime stabilized, which kept user docs
  aligned with the shipped CLI rather than with the broader specification.

## Friction Points

- `bd` parent epic closure was not automatic in every case, so backlog state
  could look incomplete even when child work was finished.
- Manual verification against the shared repo-local `instance/` tree polluted
  later checks.
- Platform-specific verification still requires environment-specific passes;
  Linux service-manager support could not be fully manual-verified on the
  current machine.

## Adjustments For The Next Cycle

### Process Lessons

1. Add an explicit "CLI help parity" check to future retrospectives and release
   checks when the spec defines a minimum command surface.
2. Add a post-execution backlog hygiene step: after a large epic closes, verify
   that parent epics are actually closed and do not rely on `bd ready` alone.
3. For timing-sensitive queue work, add tests that derive the next clock step
   from persisted timestamps instead of assuming wall-clock offsets.
4. Prefer isolated or resettable local runtime state for manual verification so
   health/recovery checks stay meaningful across sessions.

### Implementation Lessons

1. Keep action-level `structlog` instrumentation as the default pattern; it
   made runtime behavior inspectable without mixing CLI rendering concerns into
   business logic.
2. Preserve the current phase ordering for future extensions: correctness and
   inspectability first, platform management second.
3. Treat "manual verification on the real target platform" as a distinct
   acceptance dimension for native service-manager work.
