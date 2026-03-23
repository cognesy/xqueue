# Worker Lease Renewal Plan

## Goal

Close the remaining worker-runtime correctness gap where a running job can
outlive its original lease and be misclassified as stale before execution
finishes.

## Why This Matters

`SPEC.md` requires workers to renew leases while jobs are running. The current
implementation claims a job with a single `lease_expires_at` timestamp and does
not extend that lease during execution. With the current default lease values,
long-running healthy jobs can look stale and become eligible for incorrect
recovery.

## Constraints

- Keep the architecture boundary strict: `apps -> actions -> services`.
- Preserve the current command-first worker model.
- Keep JSON and CLI contracts unchanged unless new observability fields are
  strictly useful.
- Use `structlog` through action-level logging patterns already in the repo.
- Avoid introducing distributed-worker abstractions or background daemons beyond
  the current local worker runtime.

## Current Affected Areas

- `apps/cli/commands/worker.py`
- `libs/actions/workers.py`
- `libs/services/workers.py`
- `libs/services/execution.py`
- worker/runtime integration tests under `tests/actions/` and `tests/cli/`

## Approach

1. Add an explicit worker-service operation to renew an active job lease for a
   claimed running job owned by the current worker.
2. Extend the execution path so long-running commands can trigger periodic lease
   renewal while the subprocess is still active.
3. Keep cancellation and timeout handling intact so renewal stops once the
   command exits or transitions to finalization.
4. Add focused tests that prove a long-running job remains leased by the active
   worker without becoming stale.

## Risks

- Renewal timing can race with finalization if the subprocess exits while a
  renewal tick is in flight.
- Renewal must not refresh leases for jobs that are no longer owned by the same
  worker.
- Tests must be deterministic and avoid flaky wall-clock assumptions.

## Planned Task

- Implement worker lease-renewal heartbeats during command execution.
