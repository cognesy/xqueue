# Worker Runtime

This chapter is derived from the root `SPEC.md`.
`SPEC.md` remains the canonical source of truth.

## Worker Model

Workers are long-running local processes started by the operator.

Example:

```sh
xq worker --queue agent --queue maintenance --concurrency 4
```

Worker responsibilities:

- atomically lease runnable jobs
- spawn subprocesses for commands
- heartbeat while jobs are running
- capture stdout/stderr
- update attempt and job state
- honor timeout and cancel requests
- requeue or fail jobs when appropriate

Workers should support operational lifecycle states such as:

- active
- paused
- draining
- stopped

These states are distinct from job states and should be visible through CLI
inspection.

### Lease model

Job claiming must be transactionally safe.

The worker model should use leases rather than blind state flips.

At minimum:

- a worker claims one runnable job in a transaction
- the job becomes associated with that worker
- the lease has an expiry timestamp
- the worker renews the lease while the job is running
- another worker may recover the job if the lease becomes stale

This is the core crash-recovery mechanism.

Workers should heartbeat active leases while jobs are running.

### Worker crash recovery

If a worker dies unexpectedly:

- running jobs with stale leases must be detected
- those jobs must be requeued or marked failed according to policy
- recovery behavior must be visible in job history and events

The system should assume at-least-once delivery, not exactly-once execution.

## Queue Control Model

Queues are operator-visible resources.

At minimum, operators should be able to:

- list queues
- inspect queue depth and running counts
- pause a queue
- resume a queue
- purge queued jobs from a queue

Pausing a queue should prevent new jobs from being claimed while preserving
existing queued jobs.

Purging should affect only queued or retry-scheduled jobs, never silently remove
running jobs.

## Cancellation Semantics

Cancellation must be precise and unsurprising.

### Queued jobs

If a job has not started, canceling it should move it directly to `canceled`.

### Running jobs

Canceling a running job should:

1. mark cancellation as requested
2. signal the child process with `SIGTERM`
3. wait for a configurable grace period
4. escalate to `SIGKILL` if still running
5. record that the attempt ended due to operator cancellation

This is sufficient for local command execution. No more abstract cancellation
model is needed.

## Timeout Semantics

Timeout handling should mirror cancellation handling operationally.

If a running job exceeds its timeout:

1. record the timeout condition
2. send `SIGTERM` to the process group
3. wait for a configurable grace period
4. escalate to `SIGKILL` if needed
5. mark the attempt as timed out
6. either fail permanently or schedule a retry according to policy

Timeout and operator cancellation are different reasons and should remain
distinct in stored metadata.

## Retry and Failure Policy

Retries must be explicit and inspectable.

At minimum, the system should support:

- `max_attempts`
- retry delay
- optional backoff policy later

Failure outcomes should remain distinguishable:

- failed
- timed out
- canceled
- recovered after stale lease

The operator should be able to understand why a job did not succeed without
reading unstructured logs first.

An archived or dead-letter style state may be added later, but v1 can treat
permanently exhausted jobs as failed with attempt history preserved.
