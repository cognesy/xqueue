# Final Spec Gaps: March 2026

## Goal

Capture the last two remaining gaps against the original `SPEC.md` that still
look worth addressing after the earlier follow-up epic was completed:

1. make direct worker concurrency real instead of metadata-only
2. add controller-level pause-intake and resume-intake control as a distinct
   operational mode

## Review Basis

This plan is based on the latest spec-gap review after the `xqueue-ivy` follow-
up epic closed. That review narrowed the remaining drift to two items:

- `xq worker --concurrency` is accepted by the CLI, but a single worker process
  still claims and executes only one job at a time
- the controller supports `drain`, `restart`, and `stop`, but it does not yet
  expose a separate pause-intake mode as described in the spec

The user has already reviewed that assessment and asked to convert the two
items into `bd` tasks.

## Constraints

- Preserve the architecture rule: `apps -> actions -> services`.
- Keep app shells slim; CLI commands must call actions, not services directly.
- Keep action logging through `structlog`.
- Preserve current JSON output envelopes and exit-code behavior unless a task
  explicitly extends them.
- Do not weaken claim, lease-renewal, timeout, or cancellation correctness to
  achieve concurrency.
- Keep the controller a local supervisor, not a scheduler.

## Task Breakdown

### 1. Real worker concurrency

Make the existing `--concurrency` flag meaningful for direct workers. A single
worker process should be able to keep up to `N` jobs in flight while preserving
transactional claims, lease heartbeats, timeout handling, cancellation, retry
finalization, and inspectable attempt history.

Likely impact:

- [apps/cli/commands/worker.py](/Users/ddebowczyk/projects/xqueue/apps/cli/commands/worker.py)
- [libs/actions/workers.py](/Users/ddebowczyk/projects/xqueue/libs/actions/workers.py)
- [libs/services/workers.py](/Users/ddebowczyk/projects/xqueue/libs/services/workers.py)
- [libs/services/execution.py](/Users/ddebowczyk/projects/xqueue/libs/services/execution.py)
- worker execution and CLI tests

### 2. Controller pause-intake mode

Add a controller-level pause/resume intake control that is distinct from queue
pause/resume. In this mode the controller should stop causing new work to be
claimed while still exposing the state clearly through CLI/status surfaces.

Likely impact:

- [apps/cli/commands/controller.py](/Users/ddebowczyk/projects/xqueue/apps/cli/commands/controller.py)
- [libs/actions/controller.py](/Users/ddebowczyk/projects/xqueue/libs/actions/controller.py)
- [libs/services/controller.py](/Users/ddebowczyk/projects/xqueue/libs/services/controller.py)
- [libs/domain/models.py](/Users/ddebowczyk/projects/xqueue/libs/domain/models.py)
- controller action and CLI tests

## Priorities

- P1: real worker concurrency
- P2: controller pause-intake mode

## Risks

- Concurrency changes can accidentally introduce double-claim, lease-renewal,
  or cancellation races if the worker loop is expanded carelessly.
- A controller pause state can become redundant or confusing if it is not kept
  semantically distinct from queue pause and worker drain.
- Both tasks affect operator-visible behavior, so CLI/status contracts must
  stay explicit and test-covered.

## Open Questions

- Whether direct worker concurrency should be implemented with a small in-
  process slot scheduler, threads around the existing execution service, or a
  different internal structure that still preserves the current action/service
  boundaries.
- Whether controller pause-intake should pause currently supervised workers,
  switch them to a visible worker state, or leave running workers untouched and
  only suppress new claims from that point forward.
