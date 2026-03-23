# Retrospective: xqueue-7th

## Scope

Epic `xqueue-7th` closed the last two spec gaps that were previously judged
worth addressing:

1. real direct-worker concurrency
2. controller pause-intake and resume-intake mode

Both child tasks are closed and the epic is complete in `bd`.

## What Was Delivered

### Worker concurrency

- direct continuous workers now use a slot-filling threaded scheduler in
  `RunWorkerLoopAction`
- the worker registration path was hardened with an `INSERT OR IGNORE` style
  registration step to survive concurrent slot startup
- the worker docs were updated to describe real concurrency for direct
  continuous workers
- new tests prove that one worker process can execute more than one job at once

### Controller pause-intake

- controller state gained a `paused` mode
- direct-mode CLI commands now expose `pause-intake` and `resume-intake`
- controller status surfaces the paused state
- tests cover pause, resume, and interaction with stop
- user docs now distinguish controller pause-intake from queue pause

## Plan Versus Reality

The plan was accurate about the main risk areas.

- The concurrency task really did center on preserving claim, lease, timeout,
  and cancellation correctness while adding parallelism.
- The controller task stayed smaller than the concurrency task, but it still
  needed careful semantics to avoid drifting into queue-pause or scheduler
  behavior.

Two execution details mattered more than the plan made explicit:

1. concurrent slot startup exposed a real worker-registration race, which
   needed a persistence-level fix instead of a loop-only fix
2. manual controller verification is sensitive to control-file overwrites, so
   state-change commands need sequential checks rather than parallel ones

## Implementation Review

### What went well

- The repo architecture held: app shells stayed slim, actions remained the
  main logging boundary, and services stayed context-agnostic.
- `structlog` coverage remained consistent through the new action paths.
- The worker concurrency change was contained mostly to the loop action and
  worker service instead of forcing a broad rewrite of attempts or execution.
- Verification was strong: targeted tests, full-suite runs, and manual CLI
  checks were all used.

### Remaining findings

#### 1. Direct worker concurrency is still narrower than the original CLI/spec suggests

The direct worker CLI accepts `--concurrency` on both one-shot and continuous
paths, but the real concurrent execution only exists in
`RunWorkerLoopAction` when `execute_claimed` is true and `payload.concurrency >
1`.

Evidence:

- `apps/cli/commands/worker.py` still routes non-continuous execution directly
  to `RunWorkerAction`
- `libs/actions/workers.py` only enters the threaded slot scheduler from
  `RunWorkerLoopAction`

This means the original spec-level promise is only fully true for direct
continuous execution, not for every direct worker invocation that accepts
`--concurrency`.

#### 2. Paused controller mode can synthesize worker heartbeats

In paused mode, the controller loop repeatedly calls `_request_worker_state()`,
which persists worker state and updates `heartbeat_at` even though the worker
heartbeat is supposed to represent the worker process itself.

Evidence:

- `libs/services/controller.py` sets `ControllerState.PAUSED` and then calls
  `_request_worker_state(..., WorkerState.PAUSED)` every loop
- `_request_worker_state()` writes `heartbeat_at=now` through
  `WorkerService.set_worker_state()`

If a paused controller-managed worker dies, the controller status will show the
child process as exited, but the persisted worker row can still look fresh.
That weakens health semantics and can hide dead paused workers from stale-worker
checks.

## Patterns

### Rework pattern

The biggest rework came from concurrency exposing a persistence race that was
not visible in the original sequential runtime. Future concurrency tasks should
assume DB lifecycle races are likely even when the high-level algorithm looks
small.

### Smooth pattern

The action/service split made it straightforward to extend behavior without
collapsing boundaries. Logging, testing, and CLI wiring remained predictable.

## Lessons

### Process lessons

- For any task that introduces concurrency, add explicit “startup race” review
  to the execution checklist, not just “steady-state correctness”.
- For controller-state work, manual verification should avoid sending multiple
  state-change commands in parallel because the runtime control file is last-
  write-wins.
- Retrospectives on “final gap closure” epics should still re-check the
  original spec wording, not only the narrower task acceptance criteria.

### Implementation lessons

- Worker/operator CLI contracts should either be made fully real or narrowed
  explicitly. Accepting an option more broadly than it actually works creates
  avoidable ambiguity.
- Controller-owned state changes should not manufacture worker liveness signals.
  Health semantics need to stay tied to actual worker heartbeats.

## Follow-Up Work

The retrospective produced two concrete follow-ups:

- extend or narrow direct worker concurrency semantics so `--concurrency` is
  honest across direct worker modes
- stop controller pause-intake from refreshing worker heartbeats for exited or
  merely supervised workers
