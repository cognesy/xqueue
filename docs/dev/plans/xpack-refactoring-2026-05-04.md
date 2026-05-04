# xpack Refactoring Plan - 2026-05-04

## Goal

Bring `xqueue` into alignment with the x-style packaging and installed-wheel
readiness checks reported by `xpack` while preserving the SPEC.md boundaries:
`xq` stays a local-first, CLI-first durable queue, and the refactor must not
introduce distributed queue or workflow-engine abstractions.

## xpack Evidence

Commands were run from `/Users/ddebowczyk/projects/xpack` against
`/Users/ddebowczyk/projects/xqueue`:

```sh
uv run xpack scan /Users/ddebowczyk/projects/xqueue --output json --full
uv run xpack structure /Users/ddebowczyk/projects/xqueue --output json --full
uv run xpack verify /Users/ddebowczyk/projects/xqueue --output json --full
uv run xpack plan /Users/ddebowczyk/projects/xqueue --output json --full
```

Key findings:

- `xpack structure`: 5 blockers and 2 warnings.
- `xpack scan`: 0 blockers and 8 warnings.
- `xpack verify`: build, install, and `xq --help` smoke passed, but verify still
  reported 11 warnings.

Structure blockers:

- `pyproject.toml` ships top-level organization namespaces: `packages = ["apps", "libs"]`
  and `resources -> resources`.
- Root script target is `xq = "apps.cli.main:main"`.
- `apps/cli/pyproject.toml` is missing.
- `apps/cli/xqueue_cli/__init__.py` is missing.
- Production code imports top-level `apps.*` and `libs.*` namespaces.
- The shared library mapping to `xqueue_libs` is missing.

Installed-readiness warnings:

- `resources/alembic/env.py` derives a repo root from `__file__`.
- `libs/services/workspace_instance.py` sets Alembic script location to
  `repo_root / "resources" / "alembic"`.
- `libs/services/cli_bootstrap.py` derives a repo root and generates code that
  imports `apps.cli.main`.
- `libs/services/logging.py` loads `resources/logging/default.yaml` through a
  repo-relative path instead of package resources.
- `apps/cli/commands/db.py` derives a repo root for `alembic.ini`.
- The wheel contains top-level `resources/` and lacks the expected
  `xqueue_resources` package.
- `.xpack.yaml` is missing installed first-use smoke commands.

## Constraints

- Keep the CLI-first contract from SPEC.md and AGENTS.md.
- Preserve JSON/TOON/text output boundaries; Rich stays out of structured
  output paths.
- Keep SQLAlchemy ORM, Pydantic domain models, services, actions, and CLI
  concerns separated.
- Do not store mutable queue state in YAML.
- Keep stdout/stderr attempt logs in files, not DB blobs.
- Use `uv` for Python workflows.
- Use `xqa profile run default` for the shared quality lane after changes that
  affect package structure.

## Approach

Treat this as a packaging-boundary refactor, not a product feature. First create
stable project-specific import namespaces, then migrate runtime resource loading,
then lock the installed-wheel contract with `.xpack.yaml` and xpack verification.

Implementation route: mirror the `xcron` package-dir model. Physical source
directories stay ergonomic: CLI code lives directly under `apps/cli`, shared
code lives directly under `libs`, and package resources live directly under
`resources`. Setuptools maps those physical directories to installed import
names `xqueue_cli`, `xqueue_libs`, and `xqueue_resources`. The root wheel no
longer ships top-level `apps`, `libs`, or `resources` as the public installed
surface.

## Task Breakdown

1. Establish the project-specific packaging baseline.
   Update package metadata so the wheel no longer exports top-level `apps`,
   `libs`, or `resources`. Establish the intended installed namespaces:
   `xqueue_cli`, `xqueue_libs`, and `xqueue_resources`.

2. Move the CLI app behind `xqueue_cli`.
   Move or map CLI modules so the console script points at
   `xqueue_cli.main:main`, update app-internal imports, and add the app target
   metadata that `xpack structure` expects.

3. Move shared library imports behind `xqueue_libs`.
   Replace production imports from `libs.*` with `xqueue_libs.*`, including
   Alembic env and tests, while preserving the existing actions/domain/infra/
   services boundaries.

4. Move packaged resources behind `xqueue_resources`.
   Replace repo-relative resource paths with `importlib.resources`, including
   logging defaults and Alembic migrations, and remove source-checkout bootstrap
   assumptions from runtime command generation.

5. Add and verify the xpack installed-wheel smoke contract.
   Add `.xpack.yaml` safe smoke commands and prove the final structure with
   `xpack scan`, `xpack structure --fail-on blocker`, `xpack verify`, and the
   repo quality lane.

## Risks

- Import migration is broad and can break tests if source-tree and installed
  import paths diverge.
- Alembic migrations need careful handling because the migration environment is
  currently both a source-tree resource and an executable migration module.
- Controller/native service rendering may depend on `cli_bootstrap.py`; update
  tests around launchd/systemd command generation when changing it.

## Open Questions

- Whether the repo should keep one root distribution package or split the CLI
  app into a separately installable `apps/cli` project immediately. `xpack`
  reports the missing `apps/cli/pyproject.toml` as a warning, so the task should
  choose the least disruptive option that clears structure blockers first.

## Implementation Notes

- The final structure follows the `xcron` model: `apps/cli`, `libs`, and
  `resources` are the physical roots, with setuptools `package-dir` mappings to
  `xqueue_cli`, `xqueue_libs`, and `xqueue_resources`.
- `xpack structure --fail-on blocker` now passes with zero blockers. It still
  reports `structure_root_entrypoint_declared` because the root `xqueue`
  distribution intentionally remains installable as `xq`; `apps/cli/pyproject.toml`
  also declares the app-local CLI package and script contract.
- `xpack scan` and `xpack verify` pass with zero warnings after switching to the
  package-dir model. Editable imports, installed wheel imports, and packaged
  resource loading now use the same public import names without source-checkout
  shims.
- `xqa` is documented in this repo but is not installed in the current
  environment. The fallback commands from `.xqa/config.yaml` were run directly:
  `uvx ruff check apps libs tests` and `uv run pytest`.
