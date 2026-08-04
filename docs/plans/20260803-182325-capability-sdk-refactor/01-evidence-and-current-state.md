# Evidence and Current State

## Live xqueue Structure

`ast-grep outline apps libs` shows four global technical layers below a separate
CLI package:

```text
apps/cli/                 21 Python files
libs/actions/             11 Python files
libs/domain/              broad shared model and response modules
libs/infra/               SQLAlchemy engine and ORM models
libs/services/            28 Python files
```

The relevant Python tree is 9,435 lines. The largest concentration points are:

<!-- markdownlint-disable MD013 -->

| File | Lines | Structural concern |
| --- | ---: | --- |
| `libs/services/axi_contracts.py` | 659 | CLI contract metadata in a global service layer |
| `libs/domain/models.py` | 632 | 51 unrelated classes in one shared model file |
| `libs/actions/workers.py` | 597 | registry, claiming, execution, polling, and loop concerns |
| `libs/services/controller.py` | 439 | supervision and process mechanics combined |
| `libs/actions/jobs.py` | 427 | ten use cases plus file and liveness behavior |
| `apps/cli/commands/controller.py` | 359 | composition repeated in the channel |
| `libs/services/jobs.py` | 320 | persistence, mapping, query, and transition mechanics |
| `apps/cli/output.py` | 286 | valid channel concern, but dependent on global services |

<!-- markdownlint-enable MD013 -->

These are not defects merely because they are long. They identify where several
independently changing decisions are currently co-located.

## Documented Law Versus Executed Law

`docs/dev/architecture.md` declares `apps -> actions -> services` and forbids app
shells from calling services or infrastructure. The live imports contradict it:

- 15 of 21 CLI Python files import `xqueue_libs.services`;
- 11 of 21 CLI Python files import `xqueue_libs.infra`;
- `apps/cli/home.py` imports SQLAlchemy and queries `JobModel` directly; and
- command modules repeatedly construct engines, session factories, session
  managers, services, and actions.

The problem is not a missing wrapper. Composition policy and business-capability
assembly currently live in the volatile channel, so a Python SDK would either
duplicate them or import CLI code.

The service layer also does not represent one kind of hidden decision. It mixes:

- SQLAlchemy repositories and transactions;
- process execution and process-group control;
- platform service management;
- configuration and resource lookup;
- CLI renderers and command-contract metadata;
- controller orchestration;
- runtime metrics, retention, health, recovery, and hooks.

The actions are closer to the intended use-case surface, but return
`DetailResponse`, `ListResponse`, and `MutationResponse`. Those are channel
envelopes, so presentation ownership currently leaks downward.

## Existing Strengths to Preserve

- The product boundary is unusually clear and narrow in `SPEC.md`.
- Pydantic models and ORM models are already separate.
- SQLite uses explicit session and transaction helpers.
- Attempts and events preserve inspectable history.
- Process execution uses process groups for cancellation and timeout behavior.
- Machine formats bypass Rich and have regression tests.
- The test suite covers core lifecycle and operator behavior well.
- Resources, Alembic migrations, logs, and mutable state already have distinct
  ownership.

This is a refactor of dependency ownership, not a rewrite of queue semantics.

## Baseline Verification

On 2026-08-03:

- `.venv/bin/python -m pytest` collected 161 tests and all 161 passed;
- `uv run pytest` initially failed because `.venv/bin/pytest` contained a stale
  absolute shebang; reinstalling the locked pytest package repaired it, and the
  canonical command now passes all 161 tests;
- wheel and sdist builds succeed outside the worktree;
- `xqa` is not installed on `PATH`, but the sibling project provides a
  reproducible locked invocation;
- that current xqa version has replaced executable profiles with canonical
  workspace records and agent-operated native mechanism commands;
- its mechanism corpus passes all 703 verification checks;
- this repository still tracks the retired xqa pilot shape, whose Ruff lane has
  174 findings and whose Semgrep lane reports the known CLI-to-SQLAlchemy edge;
  and
- Git was clean relative to `origin/main` except the intentional `.gitignore`
  entry for the repo-local `.qmd/` index and this plan.

Stone 0 must publish the current xqa records, make the native quality commands
canonical, and resolve or explicitly ratchet the Ruff baseline. A passing
alternate invocation is evidence of current behavior, not permission to leave
the declared workflow stale.

## Namespace Consumer Evidence

A workspace-wide source and dependency scan found no Python import of
`xqueue_libs` and no xqueue dependency declaration outside this repository.
The scan excluded Git metadata, virtual environments, build output, and the
xqueue worktree itself. This supports a direct internal namespace cutover rather
than a permanent `xqueue_libs` compatibility package.

Within this repository, `ast-grep outline apps libs tests --items imports`
reports 357 `xqueue_libs` import statements across 89 files. The most frequent
targets are the shared domain models, database service, ORM/engine module, and
domain errors. That concentration confirms that Stone 1 should be one mechanical
namespace move before capability-by-capability ownership changes begin.

## Peer Architecture Evidence

### XQA

Useful patterns:

- capability-local `models.py`, `action.py`, `service.py`, and `shell.py`;
- strict typed `shell -> action -> service` flow;
- Import Linter, Tach, and architecture tests that reject global technical
  layers and forbidden dependency edges;
- independently buildable modules only where release and failure isolation are
  real requirements; and
- tests that prove the boundary checker detects synthetic violations.

Patterns not transferable to xqueue:

- a leaf process-protocol distribution;
- manifest-only extension discovery;
- bounded YAML subprocess contracts; and
- optional extension wheels and installed-extension matrices.

Those solve independent extension lifecycle and failure isolation. Xqueue owns
all of its mechanisms in one local product and has no plugin requirement.

The inspected xqa worktree was mid-rewrite and materially dirty, so the plan
copies verified principles and guardrails, not uncommitted folder names.

### Cxtk

Useful patterns:

- CLI and SDK are sibling callers of the same action surface;
- callers state intent while actions resolve contextual configuration;
- `Cxtk.open()` has typed errors, idempotent close, and no presentation effects;
- an AST boundary scanner is tested with negative fixtures; and
- Import Linter seals Typer and volatile third-party dependencies.

The current cxtk format architecture uses provider processes because parser and
renderer dependency isolation, independent installation, rollback, and crash
containment are explicit requirements. That mechanism is not appropriate for
xqueue's built-in SQLite, process, and platform adapters.

The inspected cxtk worktree was also materially dirty and implementing the
document-provider plan. Its durable contribution here is the sibling-channel,
typed-action, executable-boundary pattern.

### Xfind SDK

The xfind SDK is directionally correct:

- `Xfind.open()` owns or borrows its database explicitly;
- `close()` is idempotent and closes only owned resources;
- capability facets such as `sources`, `indexes`, `diagnostics`, `events`, and
  `runs` avoid one completely flat method list;
- CLI helpers open the public client rather than rebuilding all actions; and
- wheel/sdist tests verify public imports, typing metadata, resource access,
  eager imports, and a real installed workflow.

The execution can be improved for xqueue:

- the SDK surface spans 2,150 lines across its API files and exports a broad
  root namespace;
- `Xfind` inherits `SearchAPI` while also exposing composed facets, mixing two
  API styles;
- facet properties construct new facade objects on access rather than exposing
  one composed capability graph; and
- `apps/cli/client_ops.py` still imports `IndexReadinessService`, demonstrating
  that “CLI on SDK” needs a mechanical no-reach-around rule.

Xqueue should keep the lifecycle, typed facets, packaging tests, and CLI parity,
while using composition only, a small root export, cached facets, and enforced
channel isolation.

## Stepping Stones Principles Applied

The plan follows the local corpus in `_kb-docs/stepping-stones`:

- structure is residue of observed change pressure, not a speculative tree;
- decompose around hidden decisions, not chronological pipeline phases;
- actions are the product's use-case surface and own transactions;
- shell code parses, invokes, projects, and renders only;
- strict typed objects flow through actions and services;
- encoding and CLI envelopes are boundary projections;
- define each stone's runnable done-signal before implementation;
- use small reversible changes and delete replaced paths; and
- only split packages or processes after independent lifecycle pressure is
  demonstrated.
