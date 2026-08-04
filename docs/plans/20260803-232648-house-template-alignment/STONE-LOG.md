# Stone Log

This log records architecture decisions and verification evidence. Beads
owns task status after the plan is approved and issues are created.

## 2026-08-03 — Plan Created

Gate: awaiting user approval

Evidence:

- the house template at
  `~/projects/_kb-docs/stepping-stones/templates/agentic-python-multichannel-app`
  was read in full — eight documents plus `MODULE-ISOLATION.md`;
- xqueue satisfies seven of the template's sixteen Definition-of-Done
  items already: typed actions owning transactions, one composition root,
  a context-managed SDK with capability-grouped facets, channel-owned
  presentation, stable semantic errors, strict Pydantic models, import
  and AST and Semgrep enforcement in the default gate, mypy behind
  `py.typed`, and installed-wheel packaging tests;
- four gaps are at the process edge. Configuration is a hand-written
  single-file loader (`libs/workspace/config.py:13`) with no packaged
  defaults, user layer, environment layer, or invocation override, while
  the template makes XCFG behind an app-owned adapter mandatory;
- there is no workspace marker anywhere in `libs/`, no parent discovery,
  and no typed workspace object, so nothing validates that a directory
  belongs to xqueue;
- `typer`, `rich`, and `python-toon` are mandatory runtime dependencies
  although every import of them lives under `apps/cli/`, so an embedder
  pays for a CLI it does not use; and
- no plane map and no channel parity matrix exist, though the raw
  material does: 49 declared command contracts and 43 public facet
  methods.

Favorable finding for the configuration migration:

- XCFG's environment layer skips any variable without the nested
  delimiter (`src/xcfg/loader.py:227`), so `XQUEUE_HOME`,
  `XQUEUE_DB_PATH`, `XQUEUE_LOG_LEVEL`, and `XQUEUE_LOG_FORMAT` keep
  their current meaning and `extra="forbid"` will not begin rejecting an
  existing variable. The migration renames nothing.

Decision:

- treat this as an alignment plan, not a re-architecture. The capability
  core is what the template asks for; only the four edges change, and no
  action signature moves;
- decline the reference tree's `capabilities/`, `channels/`, and `sdk/`
  directories. The template says to adapt names to the domain and not to
  keep generic packages merely because they appear in its diagram;
  relaying out 95 modules would spend the plan on directory cosmetics;
- keep the machine-wide home instance as the default scope. xqueue is a
  single-machine queue whose controller supervises pools across projects,
  so a project workspace is additive. Absence of a marker selects home; a
  malformed or wrong-product marker is always a typed error;
- adopt XCFG behind exactly one adapter, pinned to an exact released tag,
  with no XCFG symbol in any xqueue signature or raised type; and
- give every newly declared artifact a gate. The plane map and the parity
  matrix each ship with a test that fails when the document and the code
  disagree, because the predecessor plan's own closing lesson was that a
  claim verified by a gate written after it is not verified at all.

Recorded but out of scope:

- the `jobs` table is written by five capability modules and `attempts`
  by four. The plane map names the files. Fixing it is a larger refactor
  than this plan, and pretending otherwise would repeat the drift the
  predecessor plan just finished correcting.

Next gate:

- user approval, then create the Beads epic and Stone 0 task before any
  tracked change.

## 2026-08-03 — Stone 0: Baseline, XCFG Pin, Install Decision

Gate: closed. Beads `xqueue-s93.1`.

Evidence — the baseline gate, run from a synced `uv sync --group dev`:

- `ruff check` clean; `ruff format --check` reports 189 files formatted;
- `lint-imports` — 6 contracts kept, 0 broken;
- `mypy` — no issues in 95 source files;
- `check_python_boundaries.py` passed;
- `check_architecture.py` passed with 0 allowed findings; and
- `pytest` — 209 passed in 14.3s.

Evidence — the existing Beads backlog was checked before creating
anything, and it is not empty:

- `xqueue-57w` (Level 1 module isolation) with three children already
  owns the state-ownership problem this plan's plane map recorded as out
  of scope. `xqueue-57w.1` names the same evidence — `workers/store.py`
  importing `jobs.store.JobService`, shared ORM models, several
  capabilities mutating one table. The two epics are complementary: this
  one produces `docs/dev/plane-map.md` as the input `57w.1` needs;
- `xqueue-57w.2` (composition split, module-owned ports) is partly
  satisfied already by the capability/SDK refactor and its review
  backlog, which created one composition root and made
  `JobLogPort`/`ProcessRunnerPort` real. It is left open and unedited,
  because reassessing its remaining scope belongs to that epic; and
- `xqueue-p7i` (AGENTS.md operating brief) overlaps only in that Stone 2
  edits the install command in `AGENTS.md`. No conflict.

Decision — the XCFG pin:

- XCFG is at `v0.4.1-1-g40b2f5b` with a green suite (86 passed), but
  reading `src/xcfg/loader.py` before adopting it found three contract
  defects in `_base_layer` and `matching_source_rules`, two of them
  reproduced. They are filed as `xqueue-s93.5` and must be fixed and
  released before Stone 4 can pin anything; and
- the pin will therefore be the tag that task releases — **0.5.0**, not
  a patch. Defect 1 changes the configuration an existing consumer
  receives, and a patch release should never do that silently.

Decision — the install story:

- Stone 2 proceeds as Fixed Decision 5 of the plan states. The
  documented operator install becomes `uv tool install "xqueue[cli]"`;
  embedders install `xqueue`. `xq` stays a declared console script and
  exits 2 with an actionable hint when the extra is absent. This is
  reversible in one `pyproject.toml` stanza plus four documents, and it
  is flagged to the user rather than buried here.

Next gate:

- `xqueue-s93.5` (XCFG defects) and Stones 1, 2, and 3, which are ready
  in parallel.

## 2026-08-03 — XCFG Defects Fixed Ahead of Stone 4

Gate: closed. Beads `xqueue-s93.5`. Repository
`/Users/ddebowczyk/projects/_libs/xcfg`, commit `ec7b1d4`, tag `v0.5.0`.

Evidence — three contract defects, found by reading `loader.py` before
adopting it, not by a failing suite. All 86 of XCFG's tests passed
against the defective behavior:

- `env_extends_default` reached an explicitly named config file.
  `_base_layer` branched on whether the resolved path equalled the
  packaged default, so a file passed as `config_path` or named by
  `<PREFIX>CONFIG` was merged over `config.default.yml`. Reproduced: a
  default of `{a: 1, b: 2}` and an explicit `{a: 9}` loaded as
  `{a: 9, b: 2}`. The field's own docstring scoped the flag to the named
  env layer; the code did not;
- a missing packaged default raised `cannot read <path>` rather than
  being an empty base, and did so whenever no named env was selected —
  a flag with nothing to do with whether the file exists. Every other
  absent layer is skipped; and
- `matching_source_rules` read the resolved path directly instead of
  going through `_base_layer`, so the diagnostic and `load()` disagreed
  about the same configuration.

Decision:

- the flag governs the named env layer only. A caller who names a file
  has stated the base; merging packaged defaults underneath restores
  every key they meant to omit, and no application-side code can detect
  it. This is what would have bitten xqueue: Stone 4 sets
  `env_extends_default=True` and exposes `--config`;
- a missing packaged default is an empty base on both branches. An
  explicitly named file that is missing still raises: asking for a file
  that is not there is an error, shipping no defaults is a choice; and
- released as **0.5.0**, not a patch. The first fix changes the
  configuration an existing consumer receives, and a patch release
  should never do that silently.

Verification:

- six regression tests in `tests/test_base_layer.py`, observed failing
  before the fix (5 failed, 1 passed — the one that passed guards
  against over-correcting the missing-file case);
- `just check` green: 92 passed; and
- `just release-check v0.5.0` green, wheel built and smoke-imported.

Open item:

- the tag exists **locally only**. `just release` pushes to
  `github.com/cognesy/xcfg` and triggers its release workflow, which is
  outward-facing and was not authorized, so it was not run. Until the
  user pushes it, xqueue pins the local checkout by git URL. Stone 4
  records the exact line to change.

## 2026-08-03 — Stone 1: Declared Artifacts and Their Gate

Gate: closed. Beads `xqueue-s93.2`.

Evidence — the two documents now exist and are checked:

- `docs/dev/plane-map.md`, moved from this plan directory after
  re-validating every row. All 43 facet methods are assigned to exactly
  one plane: 13 data, 12 control, 18 management;
- `docs/dev/channel-parity.md`, one row per name in `COMMAND_CONTRACTS`
  — 49 rows, of which 48 name an operation and `error` names none,
  because it is the failure envelope rather than a capability call; and
- 40 of the 43 operations are exposed on the CLI. The three that are
  not — `workers.claim`, `workers.register`, `workers.running_commands`
  — have stated reasons.

Evidence — the mapping is not one-to-one, and the document says so
rather than flattening it:

- `worker` and `worker.run` are one operation reached two ways;
- the four `workers.*` state verbs are one `set_state` with the state
  bound at registration (`apps/cli/commands/workers.py:60`); and
- `controller.stop` and `controller.restart` dispatch on `--platform`
  between `request_state` and `managed_lifecycle`.

Verification — the gate was observed failing before it was trusted:

- planted `Queues.planted` → 2 tests failed, naming `queues.planted`;
- planted a real `planted.contract` in `COMMAND_CONTRACTS` → the
  contract test failed naming it;
- deleted the `queues.stats` row → 2 tests failed; and
- each revert returned the suite to green. Total 217 passed, up from
  209.

Decision:

- planes live in `plane-map.md` only. The parity table carries no plane
  column, so there is one source of truth and no second copy to drift;
  and
- the `jobs`-table finding is recorded in `docs/dev/architecture.md`
  under a new "State Ownership" heading, naming all seven writers and
  pointing at `xqueue-57w.1`, which owns fixing it. This plan does not
  fix it and does not pretend to.

Next gate:

- Stones 2 and 3, both ready.

## 2026-08-04 — Stone 2: Packaging Split

Gate: closed. Beads `xqueue-s93.3`.

Evidence:

- `typer`, `rich`, and `python-toon` moved from `dependencies` to a `cli`
  extra, with `all = ["xqueue[cli]"]`. The base set is now `alembic`,
  `pydantic`, `pyyaml`, `sqlalchemy`, `structlog`;
- the dev group asks for `xqueue[cli]`, so `uv sync --group dev` still
  produces a working `xq` and the suite exercises both channels; and
- 96 modules type-check, up from 95: the new `xqueue_cli/entry.py`.

Decision — the guard lives in a new module, not in `main.py`:

- the plan said to guard the framework imports in `xqueue_cli.main:main`,
  but `main.py` builds the Typer app at module scope and 8 test modules
  import `app` from it. Splitting the app out would churn every one of
  them;
- instead `apps/cli/entry.py` holds the console-script entrypoint,
  imports nothing outside the standard library, and imports
  `xqueue_cli.main` lazily. `pyproject` points `xq` at
  `xqueue_cli.entry:main`, and `__main__.py` follows, so `python -m
  xqueue_cli` behaves identically; and
- the guard re-raises any `ModuleNotFoundError` whose root module is not
  one of `click`, `rich`, `toon`, `typer`. A missing extra is a hint; a
  real import bug keeps its traceback.

Verification — run by hand first, then encoded as tests:

- bare wheel in a throwaway environment: `from xqueue import Xqueue`
  succeeds; `import typer`, `import rich`, and `import toon` each fail
  with `ModuleNotFoundError`;
- `xq --help` on that install exits 2, prints
  `xq requires the cli extra: pip install "xqueue[cli]"` to stderr, and
  produces no traceback; and
- `xqueue[cli] @ file://<wheel>` then `xq --help` exits 0. The PEP 508
  direct-reference form is what uv accepts for a local wheel with
  extras; `./wheel.whl[cli]` is not parsed.

Full gate green: ruff, format, 6 contracts, mypy 96 files, boundaries,
ratchet at 0, 219 tests passing.

Next gate:

- Stone 3, which Stone 4 depends on.

## 2026-08-04 — Stone 3: The Validated Workspace

Done. `xqueue-s93.4`.

The workspace is now a thing the code names rather than a path each
caller re-derives. Five new modules under `libs/workspace/`:

- `marker.py` — `.xqueue/marker.toml` with `kind`, `schema`, and
  `created_by`, and nothing else. The database migration head stays
  Alembic's, which already owns it;
- `paths.py` — a frozen `Workspace(root, directory, scope, marker)` plus
  `derive_runtime_paths`. `root` is the directory a human would name;
  `directory` is where state lives inside it;
- `resolver.py` — the four steps: explicit root, `XQUEUE_ROOT`, upward
  discovery from a start directory, home instance;
- `init.py` — the only writer of a marker; and
- a rewritten `config.py` that takes a decided `Workspace` and reads no
  environment of its own.

Decision — absent is not an error, but broken is:

- `read_marker` returns `None` when the file is absent and raises
  `InvalidWorkspaceError` when it is present and does not check out.
  That asymmetry is the whole design: a caller may fall back past a
  workspace that is not there, and must not fall back past one that is
  broken, because operating on the wrong state root is silent data loss;
- so there is no `WorkspaceNotFoundError`. xqueue is a machine-wide
  queue whose controller supervises pools for many projects, and "no
  workspace here" is a normal answer — step 4 returns the home instance;
- a root named outright (steps 1 and 2) with no marker is *uninitialized*,
  not invalid. `workspace init`, or the first client to open it, fills it
  in. Discovery (step 3) never creates anything, because a walk that
  guesses is worse than one that finds nothing; and
- a newer `schema` is refused and an older one is accepted. This build
  understands what it has shipped and cannot know what comes next.

Decision — the home scope keeps the caller's directory as `root`:

- `Workspace.root` for a home-scope resolution is the directory the
  caller named, not `~`. Hooks and other repo-local artifacts belong to
  the project the operator is standing in even when queue state lives in
  the machine-wide instance. `workspace_root` on the runtime returns it,
  so `hooks install` is unchanged.

Decision — `Runtime.use_workspace_instance` came back as a *derived*
property:

- the controller spawns workers and launchd/systemd units that open
  their own runtime, and they must land on the workspace the parent
  decided. Both start with the workspace root as their working
  directory, so `--workspace-instance` pins them exactly there;
- it now reads `self.workspace.scope is PROJECT` rather than echoing a
  constructor argument, which closes a real gap: a client that
  *discovered* a project workspace used to spawn children that fell back
  to the home instance.

Migration — `<repo>/instance/` became `.xqueue/`:

- 77 literals across 17 files, plus `alembic.ini`, the two packaged
  skills, and the user and developer docs;
- `--workspace-instance` survives as a deprecated alias meaning "the
  workspace right here", and `config show` gained `--workspace <root>`
  as the spelling that names one; and
- `apps/cli/home.py` lost `_prefer_workspace_instance`, which probed for
  `instance/xqueue.db` to decide. Discovery answers that question now,
  and the bare `xq` view makes the same decision as every other command.

The gate caught its own subject twice, which is the point of Stone 1:
the parity test failed on `workspace.init` before either document
mentioned it, and two home-view tests failed because they seeded a bare
`.xqueue/` with no marker — correctly no longer a workspace.

Tests — 43 new, in three files:

- `tests/workspace/unit/test_marker.py` — round-trip, absent-is-None,
  newer-schema refused, older accepted, another product's marker
  refused, four malformed shapes, no temporary file left behind;
- `tests/workspace/unit/test_resolver.py` — each of the four steps with
  *every* lower-priority signal also present, so a pass means the step
  won rather than that it was the only candidate; nested discovery,
  nearest-wins, a bare `.xqueue/` ignored, and a malformed marker
  raising rather than being walked past;
- `tests/workspace/unit/test_init.py` — idempotence, partial completion,
  `--force` rewriting config while the database and logs survive, and a
  file where a directory belongs reported rather than removed; and
- `tests/workspace/integration/test_workspace_lifecycle.py` — the CLI
  command, a client opening what discovery finds, the home fallback, a
  broken marker refusing to open, and two clients on two workspaces
  enqueueing into separate databases in one process.

`tests/conftest.py` now clears `XQUEUE_ROOT`: a developer with it
exported would otherwise win step 2 and silently redirect every test at
their own workspace.

Full gate green: ruff, format, 6 contracts, mypy 101 files, boundaries,
ratchet at 0, 262 tests passing (was 219).

Next gate:

- Stone 4, now unblocked on this side. It still waits on xcfg being
  pushed, since only a local `v0.5.0` tag exists.

## 2026-08-04 — Stone 4: XCFG behind one adapter

`xcfg` is now the only thing that composes configuration, and exactly one
module imports it:

- `libs/workspace/loader.py` — a `ConfigSpec` naming `XQUEUE_CONFIG_PATH`
  as the explicit-file variable (already written by the launchd and
  systemd artifacts, and until now read by nothing) and `XQUEUE_ENV` as
  the overlay selector, plus a `SettingsLoader` that maps `ConfigError`
  onto `ConfigurationError` so no caller ever sees an xcfg type;
- `libs/workspace/settings.py` — the former `StaticConfig`, now
  `Settings`, `frozen` and `extra="forbid"`; and
- `libs/workspace/inputs.py` — `ConfigInputs`, the one shape both
  channels pass: a replacement file, an environment name, and overrides.

`libs/workspace/config.py` is gone. `resources/config/config.default.yaml`
is new and states the defaults that were previously only in the model,
with the precedence contract written at the top of it.

The chain, base first: packaged default (or an explicit file, which
*replaces* it) → named env overlay → user → workspace → environment →
`--set`. `EffectiveConfig` now carries a `layers` list, so `config show`
answers "where did this come from" without a second mechanism.

Both channels reach it the same way. `Xqueue.open` gained `env_name` and
`overrides` beside the `config_path` it already had; the CLI root
callback gained `--config`, `--env`, and repeatable `--set PATH=VALUE`.
`ConfigurationError` and `ValidationError` both map to exit code 2, and
a new group-level handler renders them: composition fails while a
command is opening its client, which is before `run_action` exists to
catch anything.

Two things worth writing down:

- `Runtime.use_workspace_instance` is now derived from the decided
  workspace rather than remembered from an argument. That closed a real
  gap — a client that *discovered* a project workspace used to spawn
  children that fell back to the home instance.
- The CLI no longer imports `click`. Typer vendored it in 0.27, so the
  installed CLI extra may not have a real `click` at all, and where one
  exists it keeps a *different* context stack from the one Typer pushes
  onto. `--config`/`--env`/`--set` are held in module state set by the
  root callback instead. `entry.py` also stopped listing `click` among
  the extra's modules: that listing turned this bug into a plausible
  "install the cli extra" message instead of the loud failure it was,
  and the packaging test was the only thing that saw it, because the dev
  environment pins typer 0.24.

Tests — 22 precedence tests, one per adjacent pair of layers plus the
failures and the properties (resolution independent of the working
directory, the flat `XQUEUE_*` variables invisible to the environment
layer because they carry no `__`); 7 layer-reporting tests; and, in the
CLI shell, one asserting the SDK and the CLI compose byte-identical
effective configuration from the same inputs.

Full gate green: ruff, format, 6 contracts, mypy 104 files, boundaries,
ratchet at 0, 292 tests passing (was 262).

Still owed, and not xqueue's to fix: xcfg `v0.5.0` exists only as a
local tag. Until it is pushed and published, `[tool.uv.sources]` in
`pyproject.toml` and `XCFG_SOURCE` in the packaging test point at the
local checkout. Both go away together; the `xcfg>=0.5.0` dependency
itself is already correct.

Next gate:

- Stone 5 — the three guardrails that keep this shape: an Import Linter
  contract confining `xcfg` to the adapter, a Semgrep rule allowlisting
  direct `os.environ` reads, and a boundary rule for the resolver.

## 2026-08-04 — Stone 5: Guardrails And Record

Gate: three rules, each observed failing on a planted violation and passing
after reverting it, then the documents brought level with the code.

Evidence — the three plantings, run against the real repository, not a
fixture, so the rule was proved on the code it governs:

- `import xcfg` in `libs/jobs/api.py` →
  `Only the workspace loader imports the configuration library BROKEN`,
  `Contracts: 6 kept, 1 broken`; reverted → `7 kept, 0 broken`.
- `os.environ.get("XQUEUE_HOME")` in `libs/jobs/api.py` →
  `unexpected architecture finding:
  xqueue-no-environment-reads-outside-resolution libs/jobs/api.py`,
  exit 1; reverted → `0 allowed findings`.
- `from xqueue.workspace.resolver import resolve_workspace` in
  `libs/jobs/api.py` → `libs/jobs/api.py:5:
  capabilities-do-not-resolve-workspaces: forbidden import
  xqueue.workspace.resolver`, exit 1; reverted → passed.

Each also has a permanent fixture, so the plantings do not have to be
repeated by hand: `tests/architecture/fixtures/import_linter/violation_xcfg/`
and two new `python_boundaries` fixtures, one violating and one legal —
naming the `Workspace` *type* stays allowed, since only deciding one is
the offence.

Decision — three notes on how the rules are drawn:

- The Import Linter contract needed `include_external_packages = True`.
  Without it the graph stops at the edge of our own packages and an
  import of `xcfg` is simply invisible, which would have made the
  contract pass by seeing nothing.
- The Semgrep exclude list is the whole rule, the same fail-closed shape
  as the SQLAlchemy one. Five files may read the environment: the
  resolver and the loader, which both take an `environ` argument and
  fall back to the real one; `workspace/instance.py`, which exports
  `XQUEUE_DB_PATH` for Alembic; logging bootstrap; and the worker
  adapter that builds a child's environment.
- The boundary rule excludes `libs/workspace/` for the obvious reason
  that the resolver lives there. It covers the five capabilities, which
  is where "which workspace am I in" would be answered a second time and
  possibly differently from the runtime that opened the client.

Documents: `architecture.md` gained a Configuration Boundary section
stating the six-layer order and the two rules that keep it, plus three
entries under Enforced Rules; `development.md` gained a Configuration
section and the warning not to import `click`; `operations.md` and
`CHEATSHEET.md` gained operator-facing precedence; `README.md` now shows
`env_name` and `overrides` on `Xqueue.open` and lists `xcfg` in the tech
stack, with PyYAML demoted to what it still does — the logging profile
and controller pool files.

Full gate green: ruff, format, 7 contracts, mypy 104 files, boundaries,
ratchet at 0, 295 tests passing (was 292).

Next gate: none — this closes the plan. What remains is not xqueue's:
xcfg `v0.5.0` exists only as a local tag, so `[tool.uv.sources]` in
`pyproject.toml` and `XCFG_SOURCE` in `tests/packaging/` still point at
the local checkout. Both are removed together once xcfg is published;
the `xcfg>=0.5.0` dependency itself is already correct and does not
change.
