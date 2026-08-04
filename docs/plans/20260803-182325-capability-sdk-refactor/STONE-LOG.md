# Stone Log

This log records architecture decisions and verification evidence. Beads owns
task status after the plan is approved and issues are created.

## 2026-08-03 — Plan Created

Gate: approved by continuation request

Evidence:

- `ast-grep outline apps libs` mapped the live xqueue code surface;
- 15 CLI files import services, 11 import infrastructure, and one imports
  SQLAlchemy directly despite the documented shell boundary;
- 161 tests pass through `.venv/bin/python -m pytest`;
- canonical `uv run pytest` is blocked by a stale absolute console-script
  shebang;
- documented xqa commands are unavailable on `PATH`;
- xqa supports capability-local code and executable module boundaries, but its
  extension workspace/process model is not earned by xqueue;
- cxtk validates the sibling CLI/SDK and typed-action pattern, while its
  provider isolation solves different requirements;
- xfind validates lifecycle, typed facets, CLI delegation, and installed SDK
  tests, while still showing the need for a no-service-reach-around rule; and
- stepping-stones principles favor a behavior-preserving sequence with named
  deltas and done-signals.

Decision:

- propose one distribution, public `xqueue` package, capability facets, one
  runtime composition root, shell-only projection, sealed concrete adapters,
  and ten dependency-ordered execution stones.

Next gate:

- create and claim the Beads epic and Stone 0 task before tracked implementation.

## 2026-08-03 — Stone 0 Readiness Rechecked

Gate: blocked on Beads remote migration ownership

Evidence:

- `uv sync --group dev --locked --reinstall-package pytest` repaired the stale
  repo-local pytest console-script shebang;
- canonical `uv run pytest` now passes all 161 tests;
- wheel and sdist builds succeed in a temporary output directory;
- root help and `jobs list --output json` smoke paths succeed;
- the sibling xqa CLI is reproducibly invocable with
  `uv run --project ../xqa --all-packages xqa ...`;
- current xqa no longer executes profiles: it initializes canonical workspace
  records, verifies mechanism packs, and leaves native tools agent-operated;
- current `xqa mechanism verify` passes all 703 checks;
- the tracked `.xqa/config.yaml`, policy, and rules belong to the retired xqa
  command model; a clean current initialization creates `workspace.yaml` and
  `catalog.lock.yaml` instead;
- the legacy Ruff command reports 174 findings in 87 files, including 83 import
  sorting findings and 58 Typer-compatible `B008` findings; and
- the native Semgrep rule pack runs cleanly as a tool but reports the one known
  CLI-to-SQLAlchemy architecture violation.

Decision:

- treat xqa as the assurance control plane and run its mechanisms through their
  native CLIs; do not preserve the retired `profile run` abstraction;
- make the Ruff baseline an explicit Stone 0 cleanup or ratchet; and
- preserve the Semgrep finding as a real red boundary until the matching stone
  removes it.

Blocker:

- Beads detected a remote-backed schema at v46 with seven pending migrations
  and requires a human decision between designated migration and adoption of an
  already migrated remote. No task write or repository implementation should
  bypass that guard.

## 2026-08-03 — Namespace Cutover Evidence

Gate: ready once the Stone 1 task can be claimed

Evidence:

- a workspace-wide scan found no external Python imports of `xqueue_libs` and
  no external dependency declarations for xqueue;
- the scan excluded Git metadata, virtual environments, build outputs, and this
  repository itself; and
- syntax-aware import outlining found 357 internal `xqueue_libs` imports across
  89 application, library, and test files.

Decision:

- cut the internal import namespace directly from `xqueue_libs` to `xqueue` in
  Stone 1 and do not add a permanent compatibility alias.

## 2026-08-03 — Stone 0 Complete

Gate: passed

Evidence:

- the designated Beads migrator upgraded the shared Dolt schema from v46 to
  v53, validation passed, and the schema plus issue graph were pushed;
- canonical `uv run pytest` passes 163 tests, including new root/group command
  inventory characterization and an isolated installed-wheel CLI smoke;
- the repository now owns a focused Ruff policy, all 117 Python files pass its
  lint and format gates, and no machine-global Ruff policy leaks into results;
- canonical xqa workspace and catalog-lock records replaced the retired
  profile-run configuration, and mechanism verification passes all 703 checks;
- the native Semgrep ratchet passes with exactly one declared baseline finding
  in `apps/cli/home.py` and fails on new or stale allowances;
- xqa doctor validates the workspace, records, resources, catalogs, docs,
  insights, and telemetry; its only remaining repository-state warning asks for
  a future assurance review after the active refactor; and
- current quality commands and package entrypoint documentation now match the
  executable tools and built artifact.

Decision:

- use xqa as a data-only assurance control plane, keep native tool execution
  explicit, and remove the final Semgrep allowance at the capability cutover
  that removes SQLAlchemy from the CLI.

Next gate:

- claim Stone 1 and cut the internal namespace to the public `xqueue` package
  before introducing runtime or capability behavior.

## 2026-08-03 — Stone 1 Complete

Gate: passed

Evidence:

- all application, library, test, migration, and package metadata imports now
  use `xqueue`; no compatibility package or live legacy import remains;
- the wheel ships `xqueue/__init__.py` and `xqueue/py.typed`, and its initial
  root `__all__` is intentionally empty until the SDK lands;
- Import Linter verifies the temporary layer direction across 50 modules and
  122 dependencies, with legal and deliberately broken fixture projects;
- the repository AST checker rejects CLI access to SQLAlchemy/sealed adapters,
  upward core imports, and adapter-to-channel imports, with fixtures for every
  rule;
- moving the home query behind `WorkerService` removed the last direct
  SQLAlchemy import from the CLI and reduced the Semgrep allowance set to zero;
- 174 tests pass, including eight AST-boundary and three Import Linter cases;
  and
- the clean-wheel check caught and then eliminated a stale ignored build tree
  that had bundled the former namespace; the regression test now rejects any
  such wheel entry.

Decision:

- keep the root export closed until `Xqueue` exists, treat the technical-layer
  Import Linter contract as a migration ratchet, and replace it with the final
  capability DAG as the capability stones complete. (The replacement was not
  done when Stone 9 closed; it was carried out afterwards under the review
  backlog. See the 2026-08-03 review-backlog reconciliation entry.)

Next gate:

- claim Stone 2 and make one lifecycle-aware runtime/client composition the
  owner of config and low-risk health reads.

## 2026-08-03 — Stone 2 Complete

Gate: passed

Evidence:

- `from xqueue import Xqueue` now exposes the sole root export without eagerly
  loading Typer, Rich, SQLAlchemy, launchd, or systemd modules;
- `Xqueue.open()` lazily creates one runtime that owns resolved configuration,
  the SQLite engine and sessions, metrics path, logging policy, health action,
  and host platform selection;
- context management, explicit close, repeated close, engine disposal, and a
  typed `XqueueClosedError` are covered by lifecycle tests;
- `workspace` and `maintenance` facets are cached per client and share the same
  runtime;
- `config show` and `health` now call those facets, with exact CLI/SDK parity
  tests for both typed payloads; and
- 179 tests plus Ruff, formatting, Import Linter, AST boundaries, Semgrep, clean
  wheel import, and installed CLI smoke pass.

Decision:

- keep runtime composition concrete and in-process, load it only from
  `Xqueue.open()`, and migrate each remaining capability onto that same owned
  runtime rather than introducing factories in individual channels.

Next gate:

- claim Stone 3 and migrate the primary jobs vertical from models through the
  SDK facet and CLI projection.

## 2026-08-03 — Stone 3 Complete

Gate: passed

Evidence:

- job actions, persistence, log handling, pruning, public models, ports, and
  the SDK facet now live under `xqueue.jobs`; the former job action/service
  modules and their import paths are gone;
- the runtime composition root assembles every job use case once, and the
  cached `xq.jobs` facet reuses those resources for enqueue, list, show, pane,
  cancel, retry, delete, tail, prune, and purge;
- job actions and SDK methods return typed job values and lists directly, while
  the CLI alone adds the stable list, detail, and mutation envelopes;
- `enqueue` and every `jobs` subcommand now use `Xqueue.open()` and `xq.jobs`,
  removing their per-command database and service assembly;
- SDK/CLI parity covers enqueue, list, and show, including cached facets and
  closed-runtime behavior; and
- 180 tests plus Ruff, formatting, Import Linter, AST boundaries, and the
  zero-allowance Semgrep ratchet pass.

Decision:

- keep presentation envelopes at the CLI edge, retain Pydantic domain values
  as the in-process contract, and compose concrete local adapters in the one
  runtime instead of exposing backend selection.

Next gate:

- claim Stone 4 and migrate queue state, statistics, pause/resume, and purge
  ownership behind the cached `xq.queues` facet.

## 2026-08-03 — Stone 4 Complete

Gate: passed

Evidence:

- queue actions, models, ports, and SQLite persistence now live under
  `xqueue.queues`; the former global queue action/service paths are gone;
  (`xqueue/queues/ports.py` was deleted afterwards: it had no importers and
  every method took the concrete session it claimed to hide. See the
  2026-08-03 decision amendment.)
- the runtime composes list, stats, pause, resume, and purge once, while the
  cached `xq.queues` facet returns queue domain values without presentation
  envelopes;
- every `queues` command and the existing `jobs purge` command now projects
  from `xq.queues`, preserving their stable CLI response shapes;
- the bare home view sources queue rows and job counts from `xq.queues.stats()`;
- queue purge depends only on public `xqueue.jobs.models`, and a fixture-backed
  architecture rule rejects imports of private jobs actions, stores, logs, or
  API internals from the queues capability; and
- queue pause/claim interaction, purge history cleanup, SDK/CLI parity, the
  full 183-test suite, Ruff, Import Linter, AST boundaries, Semgrep, and
  `git diff --check` pass.

Decision:

- model purge as queue control over purgeable public job states, expose that
  dependency explicitly through public job models, and keep the SQL deletion
  transaction sealed in the local queue adapter.

Next gate:

- claim Stone 5 and move worker lifecycle, claims, execution, output, and home
  worker projection behind `xq.workers`.

## 2026-08-03 — Stone 5 Complete

Gate: passed

Evidence:

- worker registry and atomic claim persistence, attempt lifecycle, process-group
  execution, typed models and ports, and poll/loop orchestration now live under
  `xqueue.workers`; the former global worker, attempt, and execution paths are
  gone;
- worker actions and the cached SDK facet return typed worker, claim, and poll
  results directly, while the `worker` and `workers` CLI commands preserve
  their detail, list, and mutation envelopes at the presentation edge;
- the runtime owns shared job, queue, worker, session, metric, and configuration
  dependencies and composes direct-worker runners with only command-level
  timeout, grace, and retry overrides;
- bare home worker rows and running command text now come through `xq.workers`,
  eliminating its second engine/session assembly path;
- migrated CLI shells are fixture-guarded against imports of private jobs,
  queues, or workers implementation modules;
- real subprocess execution tests cover success, retry, timeout, running-job
  cancellation, heartbeat renewal, and concurrent slots while preserving the
  SIGTERM/grace/SIGKILL process-group adapter; and
- 185 tests plus focused reliability lanes, Ruff, Import Linter, AST
  boundaries, the updated zero-allowance Semgrep ratchet, old-path scans, and
  `git diff --check` pass.

Decision:

- preserve the proven at-least-once and process-group behavior while changing
  ownership, keep SQLite claim mechanics sealed in the worker adapter, and
  expose direct operation through the same in-process runtime used by SDK and
  CLI callers.

Next gate:

- claim Stone 6 and migrate controller supervision, platform service adapters,
  pool configuration, and CLI lifecycle operations behind `xq.controller`.

## 2026-08-03 — Stone 6 Complete

Gate: passed

Evidence:

- controller policy, pool configuration, typed models and ports, direct
  supervision, and launchd and systemd adapters now live under
  `xqueue.controller`; the replaced global action and service paths are gone;
- runtime composition selects the host-specific managed-service adapter, while
  the controller SDK and CLI depend only on the public controller facet;
- controller run, status, state requests, managed lifecycle, install,
  uninstall, and pool operations all use `xq.controller`, with presentation
  envelopes added only by the CLI;
- pool mutations refresh the effective configuration of a long-lived SDK
  runtime, keeping subsequent direct status and supervision reads consistent;
- direct supervision, reconciliation, drain and restart behavior, launchd and
  systemd artifact rendering, ownership rules, and SDK/CLI parity are covered;
  and
- 186 tests plus Ruff pass after the cutover.

Decision:

- keep one direct controller policy, seal platform lifecycle details behind
  concrete adapters selected at composition, and preserve direct shell mode as
  the mandatory fallback without introducing a general supervisor abstraction.

Next gate:

- claim Stone 7 and migrate maintenance, diagnostics, configuration, workspace
  reset, metrics, home, and owned hooks behind `xq.maintenance` and
  `xq.workspace`.

## 2026-08-03 — Stone 7 Complete

Gate: passed

Evidence:

- health, doctor, database check and vacuum, stale-lease recovery, retention,
  metrics, and the home read model now live behind the typed
  `xq.maintenance` facet;
- resolved configuration, workspace-instance reset, owned hook install and
  inspection, and session-end capture now live behind `xq.workspace`;
- the runtime composes every persistence-backed maintenance action once and
  reuses the same engine, session manager, log service, metrics store, and
  effective paths used by the other capability facets;
- `db`, `doctor`, `health`, `recover`, `metrics`, `config`, hooks, and bare home
  commands now project typed SDK values and contain no SQLAlchemy, engine,
  session, configuration-loader, or service assembly;
- direct action and SDK results are channel-neutral, while CLI response
  envelopes remain stable at the shell edge;
- health degradation, stale recovery, retention, metrics, reset, home, hook
  ownership, and SDK/CLI parity tests pass; and
- 187 tests plus Ruff, formatting, Import Linter, Python boundaries, Semgrep,
  the CLI persistence scan, and `git diff --check` pass.

Decision:

- treat diagnostics and maintenance as a bounded composition over the local
  capabilities, keep mutable hook and reset operations limited to xqueue-owned
  workspace artifacts, and avoid exposing persistence objects through either
  public facet.

Next gate:

- claim Stone 8, move all presentation contracts and renderers into the CLI,
  and delete the remaining global technical-layer packages.

## 2026-08-03 — Stone 8 Complete

Gate: passed

Evidence:

- AXI metadata, response envelopes, TOON rendering, tmux rendering, field
  projection, and Rich text rendering are now owned by `xqueue_cli`;
- JSON, JSONL, TOON, and tmux serialize Pydantic values at the CLI boundary,
  while Rich remains confined to the text-output module;
- logging bootstrap and resource lookup live with runtime adapters, action
  logging lives at the runtime boundary, SQLite engine/session/ORM details live
  under the sealed `xqueue.adapters.sqlite` package (query construction stays
  with the capability persistence modules; see the 2026-08-03 decision
  amendment), and worker/controller process helpers are capability-owned;
- the global `xqueue.actions`, `xqueue.domain`, `xqueue.infra`, and
  `xqueue.services` packages and their stale bytecode are physically absent;
- Import Linter now enforces core independence, channel-neutral library code,
  and direct CLI isolation from SQLite adapters, complemented by fixture-backed
  AST boundaries and a zero-allowance Semgrep ratchet;
- explicit tests prevent the deleted global packages from returning; and
- 187 tests plus Ruff, formatting, Import Linter, Python boundaries, Semgrep,
  residue searches, directory-absence checks, and `git diff --check` pass.

Decision:

- keep presentation as a shell-channel concern, use one concrete SQLite adapter
  namespace rather than a backend extension hierarchy, and retain only
  dependency-light shared values and errors in `xqueue.core`.

Next gate:

- claim Stone 9 and verify clean wheel and sdist installs, installed SDK and CLI
  workflows, documentation, qmd, xqa, and the complete epic audit.

## 2026-08-03 — Stone 9 Complete

Gate: passed

Evidence:

- clean wheel and sdist archives contain `xqueue/py.typed`, the capability and
  SQLite packages, Alembic migrations, logging configuration, schemas, and both
  packaged skills, while the removed global technical-layer packages are
  absent;
- an initial wheel audit exposed stale setuptools `build/lib` residue that
  reintroduced deleted packages; the residue was isolated outside the checkout,
  the artifacts were rebuilt cleanly, and the installed-artifact regression now
  rejects `xqueue.actions`, `xqueue.domain`, `xqueue.infra`, and
  `xqueue.services` entries;
- wheel and sdist installations both pass exact public import and `__all__`
  checks without eagerly importing Typer, Rich, or SQLAlchemy, and their `xq`
  entry points run outside the source checkout;
- both installed artifacts initialize a temporary workspace through packaged
  Alembic resources, then complete real CLI and SDK enqueue, worker execution,
  inspect, and idempotent lifecycle-close flows;
- current architecture, development, output, user, and xqa documentation now
  describes the capability package, one `Xqueue` root, cached facets, sealed
  SQLite adapter, CLI-owned envelopes/rendering, and current native quality
  commands; (the "sealed SQLite adapter" wording overstated the boundary; see
  the 2026-08-03 decision amendment)
- Ruff lint and formatting, Import Linter's three contracts, the zero-allowance
  Python and Semgrep ratchets, YAML and Markdown lint, archive inspection,
  residue searches, `git diff --check`, and all 191 tests pass; (the gate has
  since grown to six Import Linter contracts, mypy, and 209 tests; see the
  2026-08-03 review-backlog reconciliation entry)
- xqa validates the workspace and all 79 mechanism packs; `doctor` reports only
  the expected repository-review warning because this refactor is not committed
  as an xqa review record; and
- qmd was refreshed with AST chunking active across 207 indexed Markdown,
  Python, and configuration documents.

Decision:

- ship one typed in-process capability runtime with a thin CLI channel, keep the
  artifact regression strict about physically absent legacy paths, and leave
  the source refactor uncommitted for explicit user review while Beads remains
  synchronized through the shared Dolt server.

Next gate:

- none; close Stone 9 and the capability/SDK refactor epic after recording this
  evidence in Beads.

## 2026-08-03 — Decision Amendment: SQLAlchemy Is Not Sealed

Gate: passed

Context:

- Fixed Decision 4 and the Stone 8 evidence read as "SQLAlchemy and ORM models
  are sealed inside the SQLite adapter", but eleven modules outside
  `xqueue.adapters.sqlite` import SQLAlchemy: `jobs/store.py`,
  `jobs/pruning.py`, `queues/store.py`, `workers/store.py`,
  `workers/attempts.py`, `workers/orchestration.py`,
  `maintenance/{database,health,recovery,retention}.py`, and
  `runtime/composition.py`;
- the Semgrep rule was calibrated to the narrower globs `/apps/**`,
  `/libs/core/**`, and `/libs/*/models.py`, so it passed against an arrangement
  the written decision forbade, and reported that pass as enforcement of the
  written decision.

Decision:

- amend the decision to match the code rather than move eleven modules behind a
  repository layer. SQLAlchemy is a declared runtime dependency, there is no
  embedding consumer that must avoid loading it, and there is no intent to
  change the backend or the transaction scope, so the stronger seal would buy
  indirection and nothing else;
- the sealed things are the engine, the session factory, and the ORM models,
  which stay in `xqueue.adapters.sqlite`. Query construction is allowed in the
  capability persistence modules named by an explicit allowlist and in the
  composition root, and is an error everywhere else;
- `xqueue-no-sqlalchemy-in-cli-core-models` is replaced by
  `xqueue-no-sqlalchemy-outside-persistence`, which scans all of `/apps/**` and
  `/libs/**` and excludes exactly the allowlisted files, so the rule fails
  closed: a new SQLAlchemy import anywhere else is a finding, and widening the
  allowance is an explicit edit to the rule;
- `QueueStorePort[SessionT]` is deleted. It had no importers, and every method
  took the concrete session it claimed to hide, so it advertised a boundary that
  did not exist. `JobLogPort` and `ProcessRunnerPort` are kept and are now real:
  the job, prune, tail, and retention-cleanup actions and the worker
  orchestration and execution actions annotate their dependencies with them, and
  `CleanupRetentionAction` takes `JobLogPort` as a required argument, so the
  maintenance capability no longer imports the jobs log implementation.
  `JobLogPathSource`, which nothing referenced, is deleted;
- `ProcessRunnerPort` gained `build_attempt_log_paths` and its `on_heartbeat`
  parameter was corrected to `Callable[[], object] | None`, which is what the
  implementation accepts.

Evidence:

- `rg '^(from sqlalchemy|import sqlalchemy)' libs apps` lists exactly the
  fourteen allowlisted files and nothing else;
- planting `import sqlalchemy` in `libs/jobs/api.py` makes
  `scripts/check_architecture.py` exit 1 with
  `unexpected architecture finding: xqueue-no-sqlalchemy-outside-persistence
  libs/jobs/api.py`; the ratchet passes again once the import is removed;
- Ruff lint and formatting, Import Linter (6 kept, 0 broken), mypy over 95
  files, the Python boundary checker, the Semgrep ratchet, and 209 tests pass.

Next gate:

- none; this amendment closes the SQLAlchemy question raised by the refactor
  review.

## 2026-08-03 — Review-Backlog Reconciliation

Gate: passed

Context:

- a post-completion review of this refactor filed twenty findings as
  `xqueue-4e8.1` through `.20`. All twenty are now closed. The changes they made
  are not recorded in any stone entry, so this entry is the record.

What the twenty findings changed:

- correctness: enqueue metrics were written to a second metrics file instead of
  the configured one (`.1`); `Maintenance.home` swallowed every exception (`.8`);
  `log_action` reconfigured global logging on every call (`.10`); metrics writes
  were unsafe under worker thread concurrency (`.11`); an unreachable `raise`
  ended the concurrent worker loop (`.17`); the published README SDK example did
  not run, because `enqueue` took only a model (`.14`);
- boundaries: the jobs and workers capabilities imported maintenance upward
  (`.2`); the capability DAG contract promised in Stone 1 was added, taking
  Import Linter from three contracts to six (`.3`); the CLI boundary AST checker
  enumerated files and so passed on anything it had not been told about, and now
  fails closed (`.4`); every capability `models.py` was a re-export shim over a
  640-line `core/models.py`, and the models now live with their capability, so
  `xqueue.core` holds only datetimes and errors (`.5`); the SQLAlchemy seal was
  amended to match the code and its rule rewritten to fail closed (`.6`, see the
  preceding entry); `libs/workers/sqlite.py` became `libs/workers/store.py`
  (`.20`);
- contracts: the `py.typed` promise had no type checker behind it. mypy now runs
  at `disallow_untyped_defs` over all 95 shipped modules with no baseline and no
  ignores; fixing the one typing bug it found in `log_action` cleared 86 of its
  128 initial errors, and it also surfaced a real defect — a bad
  `--created-after` value produced a raw traceback instead of a mapped error
  (`.12`); worker execution dependencies became required at construction (`.16`);
- structure: the test tree still named the deleted technical layers and is now
  filed by capability and channel, with a test that prevents the old directories
  from returning (`.13`); the twelve duplicated `Xqueue.open` call sites in the
  CLI collapsed into one `xqueue_cli.client.open_client` (`.15`); CLI
  presentation left the maintenance and workspace facets (`.9`);
- gates: the documented quality-gate command list did not match the commands
  that exist (`.18`); the packaging test recreated the stale setuptools
  `build/lib` tree it was meant to guard against, which is how deleted packages
  reached a wheel twice, and now builds from a clean tree (`.19`).

Decision:

- record the review finding itself, because it is the reusable lesson: every
  stone's evidence was verified against a gate, and each gate was scoped so that
  its claim passed. The Semgrep SQLAlchemy rule matched `/libs/*/models.py` but
  not `/libs/*/store.py`. The `core-independent` Import Linter contract passed
  because core held everything, which is the opposite of the property it was
  meant to check. The AST checker inspected an enumerated list of files, so a new
  file was compliant by omission. `py.typed` asserted a contract with no checker
  behind it. None of these gates was wrong; each was written after the claim it
  had to support, and fitted to it;
- the rule this produces: write the ratchet before the evidence, and make it fail
  closed. A gate that enumerates what to check reports the absence of a check as
  a pass. A gate whose scope is an allowlist, as
  `xqueue-no-sqlalchemy-outside-persistence` and the boundary checker now are,
  reports a new file as a finding until someone decides otherwise;
- the corollary for this log: annotate superseded claims in place with a pointer
  rather than editing them away, so the drift stays visible.

Evidence:

- Stone 1's decision, Stone 4's ports bullet, Stone 8's SQLAlchemy bullet, and
  Stone 9's documentation and gate bullets carry in-place pointers to the entry
  that supersedes them;
- `docs/dev/architecture.md` and `docs/dev/development.md` state the real
  dependency rule and the real persistence boundary;
- the current gate is Ruff lint and formatting, six Import Linter contracts,
  mypy over 95 files, the zero-allowance Python boundary and Semgrep ratchets,
  and 209 tests; all pass;
- `markdownlint` and `git diff --check` pass on the changed documents.

Next gate:

- none; the review backlog and this plan are closed.
