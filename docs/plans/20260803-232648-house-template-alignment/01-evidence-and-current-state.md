# Evidence and Current State

All observations below were checked against the working tree at the close
of the capability/SDK refactor review backlog (epic `xqueue-4e8`, twenty
of twenty findings closed).

## What Already Conforms

These are recorded so the plan does not disturb them.

| Template requirement | Where xqueue satisfies it |
| --- | --- |
| Typed action is the use case and transaction owner | `libs/*/actions.py` |
| One composition root, no policy in it | `libs/runtime/composition.py` |
| Context-managed SDK, idempotent close, typed closed error | `libs/client.py` |
| Capability-grouped typed APIs | `libs/*/api.py`, six facets |
| Channels own envelopes, projection, exit codes | `apps/cli/` |
| Stable semantic errors below the channels | `libs/core/errors.py` |
| Strict Pydantic with `extra="forbid"` | `libs/*/models.py` |
| Persistence encoding in the owning adapter | `libs/adapters/sqlite/` |
| Import contracts in the default gate | `.importlinter`, 6 contracts |
| AST boundary checker, fail-closed | `scripts/check_python_boundaries.py` |
| Zero-allowance architecture ratchet | `scripts/check_architecture.py` |
| `py.typed` backed by a checker | mypy, 95 modules, no ignores |
| Installed-wheel packaging tests | `tests/packaging/` |
| Single distribution, no premature split | `pyproject.toml` |

The capability core needs no work. Everything below is at the edge.

## Delta A — Configuration Is Hand-Written and Single-Layer

`libs/workspace/config.py:13` defines an app-local `ConfigLoader` that
reads exactly one YAML file (`_load_static`, line 90) and merges four
optional path fields over resolved defaults. There is no packaged default
file, no user layer, no environment layer for settings values, no named
environment overlay, no profile mechanism, and no invocation override.

`resources/config/` exists but holds only `.gitkeep` and `__init__.py`;
the packaged-defaults slot is reserved and empty.

The models are already strict: `StaticConfig`, `EffectiveConfig`,
`RuntimePaths`, `QueueConfig`, `WorkerDefaults`, `ControllerConfig` are
all `extra="forbid", frozen=True` (`libs/workspace/models.py`). The
validation half of the template's requirement is met; the composition
half is absent.

The template makes XCFG behind an app-owned adapter mandatory
(`WORKSPACES-AND-CONFIGURATION.md`, "Application code imports XCFG in
exactly one configuration adapter"). xqueue has no `xcfg` dependency.

### Favorable finding for the migration

XCFG's environment layer ignores any variable that does not contain the
nested delimiter (`src/xcfg/loader.py:227`, `if delimiter not in raw_key:
continue`). With `env_prefix="XQUEUE_"` and the default `__` delimiter,
today's flat variables — `XQUEUE_HOME` (`libs/workspace/config.py:44`),
`XQUEUE_DB_PATH` (`libs/workspace/instance.py:56`), and the two logging
variables read in `libs/runtime/logging.py:87` — are invisible to XCFG
and keep their current meaning. Only `XQUEUE_<SECTION>__<KEY>` becomes
live. The migration therefore does not have to rename anything, and
`extra="forbid"` will not start rejecting an existing variable.

The local XCFG checkout is `/Users/ddebowczyk/projects/_libs/xcfg` at tag
`v0.4.1`. It must be pinned to a released tag rather than tracked from
main.

## Delta B — No Validated Workspace Identity

`ConfigLoader.resolve_paths` (`libs/workspace/config.py:24`) resolves in
two modes:

- `use_workspace_instance=True` requires an explicit `workspace_root` and
  uses `<root>/instance/`; and
- otherwise `XQUEUE_HOME` or `~/.xqueue`.

There is no marker file. `rg -i marker libs` returns nothing. Nothing
validates that a directory belongs to xqueue or that its schema version
is supported. There is no parent-directory discovery, and no typed
`Workspace` object — capabilities receive `RuntimePaths` plus loose
`Path` arguments.

`apps/cli/client.py:23` passes `workspace_root or Path.cwd()`. That is
correct as a channel-edge convenience, but because nothing downstream
validates a marker, the current working directory silently determines
scope in the workspace-instance mode.

The `--workspace-instance` flag is hidden and documented as a
repo-local development aid (`apps/cli/commands/controller.py:118` and
eleven other command modules).

The template requires: a validated marker rather than a same-named
directory, the precedence chain `explicit > <APP>_ROOT > nearest
validated parent > typed error`, a typed workspace object with derived
paths, an idempotent `init` returning a typed change set, and no
process-global active workspace. Only the last of these holds today —
`Runtime` owns its paths, so two clients on different roots already
coexist in one process.

## Delta C — The Embedder Pays for the CLI

`pyproject.toml` declares `typer`, `rich`, and `python-toon` as mandatory
runtime dependencies. A program that only wants
`with Xqueue.open(...) as xq` installs all three.

They are not needed for that. Every import of the three lives under
`apps/cli/`:

```text
apps/cli/main.py, output.py, renderers/toon.py,
apps/cli/commands/*.py   (13 modules)
```

`libs/` imports none of them, and a Stone 2 test already asserts that
`from xqueue import Xqueue` does not eagerly load Typer, Rich, or
SQLAlchemy. The extras split is therefore mechanical, and the Semgrep
rules `xqueue-no-rich-outside-output` and `xqueue-no-typer-outside-cli`
already keep it that way.

The one real consequence is the console script: `xq =
"xqueue_cli.main:main"` would be installed by a bare `pip install
xqueue` and would fail on import.

## Delta D — Declared Artifacts Missing

The template requires two documents that xqueue does not have, and it
requires them to be true rather than aspirational.

### Plane map

`PLANE-MAP.md` does not exist. xqueue's behavior spans all three planes
distinctly — job execution is data, controller pools and leases and
retry are control, and doctor/db/config/hooks/metrics are management —
but no document names the state owners, the cross-plane contracts, or
the degraded behavior.

The specific question the map has to answer honestly: the `jobs` table is
written by job actions, by queue purge, by worker claim, by stale-lease
recovery, and by retention cleanup. Whether that is one state family with
one logical writer, or five writers of one table, is currently undecided
and undocumented.

### Channel parity matrix

`CHANNELS.md` requires a table recording which capabilities are exposed
on which channel and why anything is omitted, tested at the typed result
level.

xqueue has the raw material. `apps/cli/axi_contracts.py` declares 49
named command contracts, and the six SDK facets expose 43 public methods.
The CLI side is internally consistent: every literal `Output(ctx, ...)`
name in `apps/cli/` resolves to a declared contract, and
`get_command_contract` (line 596) raises on an unknown name rather than
degrading.

What is missing is the correspondence between the two surfaces. Nothing
enumerates contracts and facet methods together and asserts they agree,
and the names do not correspond mechanically — `maintenance.home` is
served by the contract `home`, and `workspace.capture_session_end` by
`hooks.session-end`. A matrix therefore has to be explicit, and once
explicit it can be enforced.

## Deviations Recorded, Not Fixed

These differ from the reference tree and are being kept deliberately.

| Template shape | xqueue shape | Why kept |
| --- | --- | --- |
| `capabilities/<name>/` | `<name>/` at package root | Same isolation |
| `channels/cli/` in-package | sibling `xqueue_cli` | Cleaner extras split |
| `sdk/apis/<name>.py` | `<name>/api.py` | Facet lives with its actions |
| `contracts/` package | none | No cross-plane process seam yet |
| `extensions/` | none | No seam has two implementations |
