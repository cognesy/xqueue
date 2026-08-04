# Migration Stones

Six stones. Each states one delta, the files it touches, and the
done-signal that closes it. Every stone keeps the full gate green and
deletes the path it replaces.

Order rationale: Stones 1 and 2 are independent, cheap, and behavior-free,
so they land first and prove the process. Stone 3 precedes Stone 4
because XCFG's project layer needs the workspace directory contract to
point at. Stone 5 is the guardrail stone, deliberately last, because a
rule written before the path is clean only records the mess.

## Stone 0 — Baseline and Decisions

**Delta:** none in code. Record what the plan assumes.

**Work:** confirm the gate is green from a clean `uv sync --group dev`;
pin the XCFG tag after reading its release notes; confirm with the user
whether the install story change in Stone 2 is acceptable, since it
changes the documented install command; create the Beads epic and tasks.

**Done-signal:** epic created; a STONE-LOG entry records the pinned XCFG
version and the install decision; no source file changed.

**Rollback:** delete the epic.

## Stone 1 — Declared Artifacts and Their Gate

**Delta:** the plane map and the channel parity matrix exist, are true,
and fail the suite when they stop being true.

**Work:**

- move `PLANE-MAP.md` from this plan directory to `docs/dev/plane-map.md`
  after validating every row against the code;
- write `docs/dev/channel-parity.md` with one row per operation, covering
  all 43 facet methods and all 49 command contracts;
- add `tests/architecture/test_channel_parity.py`, which parses the table
  and asserts correspondence in both directions;
- record the `jobs`-table writer decision reached in the plane map, in
  `docs/dev/architecture.md` under state ownership.

**Files:** `docs/dev/plane-map.md`, `docs/dev/channel-parity.md`,
`tests/architecture/test_channel_parity.py`, `docs/dev/architecture.md`.

**Done-signal:** adding a method to any facet, or a contract to
`COMMAND_CONTRACTS`, fails `pytest` with a message naming the missing
row. Verified by planting one of each and reverting.

**Rollback:** delete the test and the two documents; nothing else depends
on them.

## Stone 2 — Packaging Split

**Delta:** an embedder installing `xqueue` no longer installs Typer,
Rich, or python-toon.

**Work:**

- move the three to a `cli` extra, add an `all` extra;
- guard the framework imports in `xqueue_cli.main:main` and emit the
  actionable hint on absence;
- update `[tool.setuptools] packages` if the split changes what ships —
  it should not, since both packages stay in one distribution;
- update install instructions in `README.md`, `docs/user/README.md`,
  `docs/user/CHEATSHEET.md`, and `AGENTS.md`;
- extend `tests/packaging/integration/test_installed_artifact.py` with a
  bare-install case.

**Files:** `pyproject.toml`, `apps/cli/main.py`, four documents, one test
module.

**Done-signal:** in a clean venv, `pip install <wheel>` then
`python -c "from xqueue import Xqueue"` succeeds while `pip show typer`
fails; `xq --help` exits 2 with the hint on stderr;
`pip install "<wheel>[cli]"` then `xq --help` exits 0.

**Rollback:** move the three dependencies back; the guard is harmless if
they are always present.

## Stone 3 — Validated Workspace Identity

**Delta:** xqueue knows which workspace it is operating on, and says so
in a typed object validated against a marker.

**Work:**

- `libs/workspace/marker.py` — `WorkspaceMarker` model, read, write,
  and unsupported-schema refusal;
- `libs/workspace/resolver.py` — the four-step resolution order, with
  `WorkspaceNotFoundError` and `InvalidWorkspaceError` in
  `libs/core/errors.py`;
- `libs/workspace/paths.py` — `Workspace` and derived `RuntimePaths`;
- `Runtime.open` and `Xqueue.open` accept and pass the typed workspace;
- `xq workspace init` command and `WorkspaceInitAction` with a typed
  change set;
- map `<repo>/instance/` onto `.xqueue/`, keep `--workspace-instance` as
  a deprecated alias, delete the second branch of `resolve_paths`.

**Files:** four new modules in `libs/workspace/`, `libs/core/errors.py`,
`libs/runtime/composition.py`, `libs/client.py`, `apps/cli/client.py`,
`apps/cli/commands/` (new `workspace` group), `libs/workspace/config.py`.

**Done-signal:** a new `tests/workspace/` lane covers marker round-trip,
unsupported-version refusal, all four resolution steps in precedence
order, discovery from a nested directory, a same-named directory with a
malformed marker raising rather than falling back, idempotent init,
non-destructive `--force`, and two clients on different workspaces in one
process.

**Rollback:** the resolver is additive until the `resolve_paths` branch
is deleted; that deletion is the last commit of the stone and is the
revert point.

## Stone 4 — XCFG Adapter and Layered Precedence

**Delta:** configuration composes from packaged, user, workspace,
environment, and invocation layers through one adapter, instead of one
YAML file.

**Work:**

- add the pinned `xcfg` dependency;
- `resources/config/config.default.yaml` stating every default;
- `libs/workspace/settings.py` — `Settings`, from today's `StaticConfig`,
  unchanged in shape and still `extra="forbid"`;
- `libs/workspace/loader.py` — `SPEC` and `load_settings`, the only
  module importing `xcfg`, mapping `xcfg.ConfigError` to
  `ConfigurationError`;
- CLI gains `--config`, `--env`, and repeatable `--set path=value` at the
  root callback, passed through `open_client`;
- delete `libs/workspace/config.py`.

**Files:** `pyproject.toml`, `resources/config/config.default.yaml`, two
new modules, `apps/cli/main.py`, `apps/cli/client.py`,
`libs/runtime/composition.py`, `libs/workspace/config.py` (deleted).

**Done-signal:** a `tests/workspace/` configuration lane covers every
adjacent precedence edge from the contract in
[`02-target-architecture.md`](02-target-architecture.md), unknown keys
mapped to `ConfigurationError`, a named environment overlay, resolution
that does not depend on the test working directory, and equal settings
when opened through the SDK and through the CLI. `config show` reports
the layer order it used.

**Rollback:** `config.py` is deleted only after the new lane passes; the
revert restores one file and one dependency line.

## Stone 5 — Guardrails and Record

**Delta:** the newly cleaned paths become rules, and the documents match.

**Work:**

- Import Linter contract: only `xqueue.workspace.loader` imports `xcfg`;
- Semgrep rule: `os.environ` and `getenv` outside the four allowlisted
  modules is an error, in the same fail-closed exclude style as
  `xqueue-no-sqlalchemy-outside-persistence`;
- boundary checker: capability modules may not import the resolver;
- verify each new rule fails on a planted violation before trusting it;
- update `docs/dev/architecture.md`, `docs/dev/development.md`, and
  `docs/user/` for the new install, workspace, and configuration
  contracts;
- STONE-LOG entries for every stone, and a closing entry.

**Files:** `.importlinter`, `.semgrep/xqueue-architecture.yml`,
`scripts/check_python_boundaries.py`, four documents, `STONE-LOG.md`.

**Done-signal:** each of the three new rules has been observed failing on
a planted violation and passing after reverting it; the full gate is
green; `markdownlint` and `git diff --check` pass.

**Rollback:** rules are removable individually without touching source.

## Sequencing Constraints

```text
Stone 0 ---> Stone 1 -----------------> Stone 5
        \--> Stone 2 -----------------/
        \--> Stone 3 ---> Stone 4 ----/
```

Stones 1, 2, and 3 may proceed in parallel. Stone 4 requires Stone 3.
Stone 5 requires everything, because it writes the rules that describe
the finished state.
