# Proposed Beads Epic and Tasks

This is the reviewed creation specification. Do not create these issues until
the plan review gate in `README.md` is approved. Once created, Beads is the
canonical status and dependency tracker.

## Epic

Title: Refactor xqueue to capability architecture with a first-class SDK

Type: epic  
Priority: P1

Description:

> Replace global technical layers and CLI-side dependency assembly with one
> capability-oriented xqueue core, one runtime composition policy, a typed
> lifecycle-safe Python SDK, thin CLI projections, concrete adapter isolation,
> and executable architecture/package/reliability guardrails. Preserve every
> current queue, worker, controller, persistence, output, and CLI contract.

Epic acceptance:

- `from xqueue import Xqueue` is a tested installed-artifact contract;
- CLI and SDK share canonical typed actions and runtime composition;
- CLI imports no adapters, SQLAlchemy, or private capability code;
- global action/domain/infra/service packages are gone;
- current CLI/machine-output and worker reliability semantics are preserved;
- the final full gate matrix passes; and
- no plugin, extension process, alternate broker, or distributed abstraction is
  introduced.

## Child Tasks

### Task 1: Restore canonical quality and characterization baseline

Type: task  
Priority: P0  
Dependencies: epic only

Acceptance:

- stale uv console scripts are repaired;
- documented xqa commands are reproducibly invocable;
- full pytest and xqa gates pass;
- CLI/output/reliability characterization fixtures are stored; and
- existing installed artifact smoke passes.

### Task 2: Establish public xqueue package and executable boundaries

Type: task  
Priority: P0  
Dependencies: Task 1

Acceptance:

- public namespace is `xqueue` with `py.typed` and small `__all__`;
- package metadata and installed imports pass;
- Import Linter and AST rules enforce the initial dependency law;
- each rule has failing and legal fixtures; and
- current behavior suite remains green.

### Task 3: Implement runtime composition and SDK lifecycle

Type: feature  
Priority: P0  
Dependencies: Task 2

Acceptance:

- one composition root owns config and runtime resources;
- `Xqueue.open`, context manager, idempotent close, and closed error work;
- cached facet construction is tested;
- pilot config/health CLI calls use the client; and
- source and installed SDK lifecycle tests pass.

### Task 4: Migrate the jobs capability and CLI surface

Type: feature  
Priority: P0  
Dependencies: Task 3

Acceptance:

- job models, ports, actions, adapters, and API are capability-owned;
- enqueue and all jobs commands use `xq.jobs`;
- action results contain no CLI envelopes or ORM objects;
- SDK/CLI parity and all job lifecycle tests pass; and
- old jobs action/service paths are deleted.

### Task 5: Migrate queues capability

Type: feature  
Priority: P1  
Dependencies: Task 4

Acceptance:

- queue models, actions, ports, adapter, and API are capability-owned;
- queue commands and home queue data use `xq.queues`;
- permitted queue-to-job contracts are enforced; and
- queue/purge/parity tests pass with old paths deleted.

### Task 6: Migrate and split worker runtime

Type: feature  
Priority: P0  
Dependencies: Task 4, Task 5

Acceptance:

- registry, claim, attempt, process, and loop responsibilities are explicit;
- worker commands use shared composition;
- atomic claim, lease, retry, timeout, cancellation, process-group, heartbeat,
  and stale recovery tests pass; and
- old worker action/service paths are deleted.

### Task 7: Migrate controller and platform adapters

Type: feature  
Priority: P1  
Dependencies: Task 6

Acceptance:

- controller policy is capability-owned;
- launchd/systemd are selected adapters outside CLI;
- controller and pool commands use `xq.controller`;
- direct/managed lifecycle and ownership tests pass; and
- old controller paths are deleted.

### Task 8: Migrate maintenance and workspace capabilities

Type: feature  
Priority: P1  
Dependencies: Task 5, Task 6, Task 7

Acceptance:

- health, doctor, recovery, DB maintenance, retention, metrics, home, config,
  reset, and hooks are on capability APIs;
- CLI has no remaining dependency assembly or persistence access;
- owned-artifact and degraded-health behavior is preserved; and
- old paths are deleted.

### Task 9: Reclaim presentation and remove global technical layers

Type: task  
Priority: P1  
Dependencies: Task 8

Acceptance:

- AXI metadata and all renderers are CLI-owned;
- Rich is text-only and machine formats serialize typed results directly;
- action results have no CLI response envelopes;
- global `actions`, `domain`, `infra`, and `services` packages are absent; and
- output and architecture gates pass.

### Task 10: Verify clean artifacts, document, and audit completion

Type: task  
Priority: P0  
Dependencies: Task 9

Acceptance:

- wheel/sdist public import, typing, resources, and eager-import checks pass;
- installed SDK/CLI enqueue-worker-inspect smoke passes;
- full pytest and xqa gate matrix passes;
- architecture and SDK docs describe the live system;
- completion audit finds no residue or incomplete acceptance; and
- epic and all tasks are closed only after Git and Beads sync verification.

## Dependency Graph

```text
1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10
                  \---------> 6
                       \-----> 8
```

The mostly sequential graph is deliberate. Capability cutovers touch shared
model and composition seams; parallel execution would increase conflicting
dual paths and weaken per-stone verification. Narrow subtasks inside one Beads
issue may be parallelized only when they edit disjoint files and share a fixed
contract.

## Beads Preflight

The current Beads store cannot create or reliably query tasks yet. `bd status
--json` reported a pending schema migration over a dirty `comments` table and
instructed running `bd dolt commit`; `bd search` also observed the pre-migration
schema. Before issue creation:

1. inspect `bd dolt status` and the pending working set;
2. preserve existing data;
3. commit the current Dolt schema working set as instructed by Beads;
4. rerun the migration/status command;
5. verify existing issues are readable; and
6. only then create the epic, tasks, and dependency edges.

Do not reinitialize or delete Beads state as a shortcut.
