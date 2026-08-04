# Capability Architecture and SDK Refactor

Status: proposed for human review  
Created: 2026-08-03 18:23 CEST  
Scope: behavior-preserving modularization of the existing xqueue product

## Outcome

Refactor xqueue from global technical layers with channel-side composition into
one capability-oriented core with:

- one composition policy shared by every runtime;
- a typed, lifecycle-safe Python SDK as a first-class surface;
- CLI commands that parse, call the SDK or its underlying actions, and project
  results without constructing persistence or services;
- capability-owned models, actions, ports, and APIs;
- concrete SQLite, process, filesystem, configuration, and platform mechanisms
  isolated behind the capabilities that consume them; and
- executable import, package, CLI/SDK parity, and reliability guardrails.

The refactor preserves the CLI command surface, TOON default, stable JSON and
JSONL contracts, SQLite/Alembic state, process-group semantics, retries,
timeouts, cancellation, stale-lease recovery, and single-machine operating
model.

## Architecture Decision

Use one distribution and one importable core package. Do not create a uv
workspace, independently released internal modules, a plugin system, provider
discovery, or process protocols. XQA and cxtk demonstrate those mechanisms for
independently evolving extensions; xqueue has no corresponding product pressure
and explicitly lists plugins as a non-goal.

The public embedding contract will be:

```python
from xqueue import Xqueue

with Xqueue.open(workspace_root="/repo") as xq:
    job = xq.jobs.enqueue(
        queue="agent",
        command="python scripts/check_mailbox.py --agent writer-1",
    )
    status = xq.jobs.show(job.id)
```

The class is a lifecycle and composition facade, not a second implementation of
the product. Capability facets call the same typed actions used by the CLI.

## Fixed Decisions

1. The action remains the canonical use-case boundary and transaction owner.
2. SDK results are typed domain results, not CLI envelopes or encoded payloads.
3. CLI-only envelopes, field projection, Rich, TOON, JSON, JSONL, and tmux
   rendering stay in the CLI package.
4. The engine, the session factory, and the ORM models are sealed inside
   `xqueue.adapters.sqlite`. SQLAlchemy query construction is not: it is allowed
   in the capability persistence modules named by the Semgrep allowlist and in
   the composition root, and is an error everywhere else — in every `api.py`,
   `models.py`, and `actions.py`, in `xqueue.core`, and in the CLI. Amended
   2026-08-03; see the STONE-LOG entry for why the stronger claim was dropped.
5. Typer and Rich are sealed inside the CLI channel.
6. Job execution remains shell-command and process-group based.
7. SQLite remains the only canonical mutable state store; the adapter boundary
   hides implementation knowledge but does not advertise unsupported databases.
8. Capability dependencies are explicit and directional. Cross-capability use
   goes through public models, ports, or actions, never private modules.
9. The public `xqueue` package has a deliberately small `__all__`; detailed
   request and result types live with their capability.
10. Every migration stone must keep the full behavior suite green and remove
    the old path it replaces.

## Explicit Non-Goals

- no distributed worker abstraction;
- no alternate broker or database backend;
- no callable/job plugin model;
- no entry-point discovery or executable extensions;
- no web or REST channel;
- no workflow/DAG or scheduling concepts;
- no big-bang rewrite; and
- no permanent compatibility layer for the private `xqueue_libs` import name.

## Documents

- [Evidence and current state](01-evidence-and-current-state.md)
- [Target architecture](02-target-architecture.md)
- [Migration stones](03-migration-stones.md)
- [Verification and rollback](04-verification-and-rollback.md)
- [Proposed Beads epic and tasks](05-beads-execution-map.md)
- [Stone log](STONE-LOG.md)

## Review Gate

Human approval is required before creating the Beads epic. Review should
confirm these four consequential choices:

1. adopt `from xqueue import Xqueue` as the public SDK namespace;
2. keep one distribution rather than copying xqa/cxtk workspace isolation;
3. use capability facets rather than a flat client with every operation; and
4. migrate in behavior-preserving stones, deleting each replaced global-layer
   path before advancing.

After approval, Beads becomes the execution authority. This plan remains the
architecture and acceptance record, not a parallel task tracker.
