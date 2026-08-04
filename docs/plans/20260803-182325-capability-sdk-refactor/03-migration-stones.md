# Migration Stones

Each stone is independently reviewable, keeps the product runnable, has a named
improvement delta, and deletes the path it replaces. Beads dependencies mirror
this order after plan approval.

## Stone 0: Restore the Canonical Baseline

Purpose: make the declared verification commands trustworthy before structural
change.

Work:

- rebuild the repo-local uv environment so console-script shebangs point at the
  current repository path;
- establish a reproducible sibling-project invocation for the current xqa CLI;
- replace the legacy xqa pilot records with the current canonical workspace
  records, preserving the native Ruff, pytest, and Semgrep commands as explicit
  agent-operated gates;
- run `xqa doctor`, `xqa mechanism verify`, Ruff, pytest, and the repository
  Semgrep rules directly;
- run the full pytest suite through the canonical uv command;
- capture current CLI help, command inventory, exit codes, and representative
  TOON/JSON/JSONL/text outputs as characterization fixtures; and
- add an installed-package smoke for the existing wheel before changing its
  namespace.

The legacy Ruff configuration currently reports 174 findings across 87 files.
Stone 0 must either resolve that bounded baseline or publish an explicit ratchet;
it must not silently declare the existing red lane green. The existing Semgrep
rules likewise correctly expose the known CLI-to-SQLAlchemy boundary violation.

Delta: canonical gates run from a clean checkout and current behavior has an
executable oracle.

Done signal: all declared baseline commands run successfully, or a clearly
scoped product-independent tool defect is recorded with an equivalent
reproducible gate approved in Beads.

## Stone 1: Establish the Public Package and Boundary Enforcer

Purpose: create the namespace and executable rules that later stones move into.

Work:

- map `libs/` to the `xqueue` import package and cut internal imports from
  `xqueue_libs` to `xqueue` in one mechanical change;
- add a small root `__all__` and `py.typed`;
- add Import Linter contracts and a repository-specific AST scanner;
- forbid CLI imports of adapters/SQLAlchemy and forbid upward imports from core;
- add negative fixtures for every rule; and
- update packaging metadata and installed import tests.

No permanent `xqueue_libs` compatibility alias is added. A workspace-wide scan
found no consumers outside this repository, and `xqueue_libs` has not been a
documented public SDK.

Delta: the intended public namespace exists and architecture rules can fail.

Done signal: source and installed-wheel imports work as `xqueue`, every negative
fixture is detected, and all baseline behavior remains green.

## Stone 2: Add One Composition Root and SDK Lifecycle

Purpose: remove dependency assembly policy from channels without moving all
capabilities at once.

Work:

- introduce runtime composition for config, engine, unit-of-work factory,
  filesystem paths, metrics, logging, and platform selection;
- implement `Xqueue.open()`, context management, idempotent close, and typed
  use-after-close error;
- create cached empty/pilot capability facets;
- expose configuration and a low-risk health/config read through the SDK; and
- make the corresponding CLI commands use the client.

Delta: CLI and future embedders share one resource/lifecycle policy.

Done signal: lifecycle tests, resource ownership tests, SDK/CLI parity for pilot
reads, and a clean installed-wheel SDK smoke pass.

## Stone 3: Migrate the Jobs Capability as the Vertical Pilot

Purpose: prove the full capability shape on the product's primary noun.

Work:

- localize job, attempt, event, input, filter, and result models;
- split job use cases into focused actions with strict input/result contracts;
- introduce narrow job unit-of-work/store ports and their SQLite implementation;
- move file-tail and pane liveness behind job-owned ports/adapters;
- expose a cached `xq.jobs` SDK facet;
- cut `enqueue`, `jobs *`, and the job portion of home to the facet; and
- move list/show/mutation envelope construction to CLI projection.

Delta: the primary business capability is independently understandable and no
job CLI command constructs persistence or services.

Done signal: job action, persistence, CLI contract, SDK parity, concurrency,
history, and installed-package tests pass; old job action/service paths are
deleted.

## Stone 4: Migrate Queues

Purpose: isolate queue control and its deliberate dependency on job state.

Work:

- localize queue models, actions, ports, and SQLite adapter;
- make queue purge policy explicit at the capability boundary;
- expose `xq.queues`;
- cut queue commands and queue home projection to the SDK; and
- encode the permitted `queues -> jobs` dependency mechanically.

Delta: queue operations no longer rely on global services or ORM knowledge.

Done signal: queue state, stats, pause/resume, purge, SDK/CLI parity, and
concurrent claim interaction tests pass; old queue paths are deleted.

## Stone 5: Split and Migrate Worker Runtime

Purpose: isolate the highest reliability risk before touching supervision.

Work:

- separate worker registry/state, atomic claiming, attempt lifecycle, command
  execution, and long-running polling loop;
- localize worker and execution models;
- place SQL claim/update mechanics in the SQLite adapter;
- place process spawn/group/timeout/termination mechanics in the process
  adapter;
- expose `xq.workers` for state operations and direct worker execution; and
- cut worker and workers commands to the shared composition.

Delta: worker orchestration reads as composition of explicit contracts and the
current 597-line action concentration is removed.

Done signal: atomic-claim races, retries, timeout, queued/running cancellation,
SIGTERM-to-SIGKILL escalation, heartbeats, stale lease behavior, direct worker
CLI, and SDK lifecycle tests pass; obsolete worker files are deleted.

## Stone 6: Migrate Controller and Platform Adapters

Purpose: separate supervision policy from OS service mechanics.

Work:

- localize controller pool/state/config models and use cases;
- split worker-process supervision from launchd/systemd management;
- compose managed platform adapters in runtime, never in CLI commands;
- expose `xq.controller`; and
- cut all controller commands and pool operations to the facet.

Delta: one controller policy drives direct and managed modes while platform
details remain replaceable mechanisms.

Done signal: controller state transitions, pool reconciliation, restart/drain,
artifact ownership, launchd/systemd rendering, direct fallback, SDK/CLI parity,
and installed invocation tests pass; old controller paths are deleted.

## Stone 7: Migrate Maintenance and Workspace Capabilities

Purpose: remove remaining cross-cutting service and channel assembly.

Work:

- migrate health, doctor, stale recovery, DB check/vacuum, retention, metrics,
  home read model, resolved configuration, workspace reset, and hooks;
- keep health/doctor as bounded compositions over public capability ports;
- keep hook mutation ownership explicit and confined to owned artifacts;
- expose `xq.maintenance` and `xq.workspace`; and
- cut every remaining operator command to the SDK/composed action surface.

Delta: no CLI module reaches infrastructure or business services, including
home and hooks.

Done signal: all operator commands, hook ownership cases, database maintenance,
recovery, metrics, health/doctor, home degradation behavior, and SDK/CLI parity
tests pass; remaining old action/service paths are deleted.

## Stone 8: Reclaim Presentation and Observability Boundaries

Purpose: finish the shell-only projection rule and remove technical-layer
residue.

Work:

- move AXI contract metadata and TOON/tmux rendering under `xqueue_cli`;
- ensure JSON/JSONL/TOON paths serialize typed results without Rich;
- keep text and tmux rendering channel-local;
- remove response envelopes from core action returns;
- isolate structlog configuration and resource lookup in runtime adapters; and
- eliminate the global `actions`, `domain`, `infra`, and `services` packages once
  all ownership has moved.

Delta: the source tree communicates product capabilities rather than technical
buckets, and every machine output is a boundary projection.

Done signal: no forbidden global-layer packages remain, output golden tests and
error/exit contracts pass, and architecture gates report the exact target DAG.

## Stone 9: Installed Contract and Final Audit

Purpose: prove the refactor works as shipped, not only from the source tree.

Work:

- build wheel and sdist in clean temporary environments;
- verify `from xqueue import Xqueue`, exact root `__all__`, and `py.typed`;
- verify import does not eagerly load Typer, Rich, or platform managers;
- run enqueue -> worker -> inspect through the installed SDK and CLI;
- run direct and controller-mode smoke tests appropriate to the host;
- run every xqa and pytest gate;
- update architecture/user/SDK documentation; and
- audit the Beads epic for incomplete acceptance criteria or residual paths.

Delta: public import, CLI, persistence, resources, and reliability contracts are
demonstrably valid in the built artifact.

Done signal: the entire verification matrix passes from clean artifacts, no old
architecture path remains, documentation matches executable behavior, and the
epic completion audit finds no open or blocked requirement.
