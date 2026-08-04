# Plane Map

Completed against xqueue's real actions, not an imagined component list.

Every name below is a public method on an SDK facet.
`tests/architecture/test_channel_parity.py` asserts that each of the 44
methods appears in exactly one plane and that
[`channel-parity.md`](channel-parity.md) agrees with the assignment, so
this document cannot quietly fall behind the code.

## System Boundary

**System:** xqueue — a single-machine durable work queue for shell
commands, used through a CLI and an embedded Python SDK.

**Primary value delivered:** a shell command handed to xqueue runs
exactly once to a terminal state, survives process death, and can be
inspected, cancelled, retried, and reaped afterwards.

**Last-known-good safety window:** none is claimed. Control and data run
in the same process group against the same SQLite file. A worker holds a
lease for its configured duration and finishes the job it has claimed
even if the controller dies, but that is a property of process
independence, not of a versioned policy snapshot. This is stated plainly
so that no document implies an availability guarantee the code does not
provide.

## Plane Assignment

Data — primary work on one job:

```text
jobs.enqueue      jobs.list      jobs.show     jobs.pane
jobs.tail         workers.claim  workers.run   workers.register
workers.list      workers.running_commands     queues.list
queues.stats      maintenance.home
```

Control — steering which work runs, where, and when:

```text
queues.pause          queues.resume        jobs.cancel
jobs.retry            workers.set_state    controller.run
controller.status     controller.request_state
controller.list_pools controller.ensure_pool
controller.remove_pool
maintenance.recover_stale_leases
```

Management — configuring, observing, repairing, and evolving:

```text
workspace.init             workspace.config
workspace.reset_instance
workspace.install_hooks    workspace.hook_status
workspace.capture_session_end
maintenance.health         maintenance.doctor
maintenance.check_database maintenance.vacuum_database
maintenance.cleanup_retention
maintenance.metrics        maintenance.reset_metrics
controller.install         controller.uninstall
controller.managed_lifecycle
jobs.delete                jobs.prune            queues.purge
```

Two assignments deserve their reasoning:

- `controller.install`, `uninstall`, and `managed_lifecycle` are
  management, not control, because they mutate launchd and systemd
  artifacts owned by the operator's machine rather than xqueue's own
  scheduling state.
- `jobs.delete`, `jobs.prune`, and `queues.purge` are management, not
  data, because they destroy history rather than advance work.

## Authoritative State and Writers

| State family | Sole writer today | Single-writer? |
| --- | --- | --- |
| `queues` table | `queues/store.py` | yes |
| `workers` table | `workers/store.py` | yes |
| `events` table | five modules, append-only | acceptable |
| `jobs` table | five capability modules | **no** |
| `attempts` table | four capability modules | **no** |
| attempt log files | `workers/process.py` writes | by convention |
| metrics file | `adapters/filesystem/metrics.py` | yes, one adapter |
| config file | operator plus `workspace init` | yes after Stone 3 |
| launchd/systemd artifacts | `controller/{launchd,systemd}.py` | yes |

`maintenance/health.py` imports `WorkerModel` but only reads it
(`libs/maintenance/health.py:148`), so it is not a second writer.

## The Multiple-Writers Finding

The `jobs` table is written by `jobs/store.py`, `jobs/pruning.py`,
`queues/store.py`, `workers/store.py`, `workers/attempts.py`,
`maintenance/recovery.py`, and `maintenance/retention.py`. The `attempts`
table is written by four of those. The template's rule is that every
durable state family has one logical writer, and this one has five.

The honest assessment:

- the writes are not arbitrary. Each is a legitimate transition of the
  job lifecycle — claim, complete, cancel, expire a lease, delete — and
  each happens inside one action's transaction against one SQLite file
  with `foreign_keys=ON` and WAL;
- the risk today is low. One machine, one database, one process group,
  and the atomic claim is a single guarded `UPDATE`; and
- the risk is not zero, and it grows with every new capability that finds
  it convenient to reach for `JobModel`. Nothing currently prevents that:
  the SQLAlchemy allowlist decided in the predecessor plan permits
  capability persistence modules to build queries, and says nothing about
  which tables each may touch.

This is the state-ownership violation to remove, and it is deliberately
**not** in this plan's scope. Recording it here, with the file list, is
the point of writing a plane map at all.

## Cross-Plane Contracts

There are none, and that is the accurate answer rather than an omission.
Every plane reads and writes the same SQLite database directly. There is
no versioned policy snapshot, no bounded outcome summary, and no queue
between planes.

The one seam that behaves like a contract is the worker lease: the
controller does not interrupt a claimed job, and a worker's claim is
valid until `lease_expires_at` regardless of what the control plane does
afterwards. It is enforced by `workers/store.py`'s conditional update,
not by a declared schema.

## Degraded Behavior

- **Controller stops** — running workers finish claimed jobs, no new
  pool slots start, and queues keep accepting enqueues.
- **Worker dies mid-job** — the lease expires and
  `recover_stale_leases` returns the job to a retryable state.
- **Management commands fail** — data and control continue; nothing
  depends on `doctor`, `metrics`, or `health`.
- **Database unavailable** — every plane stops with
  `StateStoreUnavailableError`. There is no degraded mode, and none is
  claimed.
- **Config file malformed** — startup fails before any action runs;
  after Stone 4 with a mapped `ConfigurationError`.

The fourth case is the one that matters: xqueue makes no claim of
independent plane operation, because all three planes share one SQLite
file. The template asks for failure drills only "at the earned separation
level"; xqueue has not earned it and should not pretend otherwise.

## Channel Exposure

Every capability is exposed on both channels that exist. REST and web are
absent by decision, not by omission.

| Plane | SDK | CLI | REST | Web |
| --- | --- | --- | --- | --- |
| Data | yes | yes | no | no |
| Control | yes | yes | no | no |
| Management | yes | yes | no | no |

Two operations are intentionally asymmetric and the parity matrix records
why: `workspace.capture_session_end` is exposed as the hidden CLI command
`hooks session-end`, invoked by agent hooks rather than by an operator,
and `workers.claim` exists on the SDK for embedders that drive their own
loop while the CLI exposes only the composed `worker run`.

## Next Earned Separation

**Smallest useful seam:** one declared writer per table, enforced the same
way the SQLAlchemy allowlist is enforced — a rule naming which capability
persistence module may import which ORM model. That is a Semgrep or
boundary-checker rule over `libs/*/[a-z]*.py` importing
`xqueue.adapters.sqlite.models`, and it needs no runtime change.

**Verification:** plant a `JobModel` import in a capability that does not
own it and confirm the gate fails.

**Physical split justified now?** No. There is no measured availability,
authority, scale, or team pressure, and a second process would add a
network or file protocol between two halves of a single-machine tool.
