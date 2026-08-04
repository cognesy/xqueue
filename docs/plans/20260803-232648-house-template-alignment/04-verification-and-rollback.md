# Verification and Rollback

## Gate Composition

Every stone must leave this green. The list is the canonical one from
`AGENTS.md` and `docs/dev/development.md`.

```bash
uvx ruff check apps libs tests scripts
uvx ruff format --check apps libs tests scripts
uv run lint-imports
uv run mypy
uv run python scripts/check_python_boundaries.py
uv run python scripts/check_architecture.py
uv run pytest
```

Documentation stones additionally run:

```bash
markdownlint <changed files>
git diff --check
```

Baseline at the start of this plan: Ruff clean, 6 Import Linter contracts
kept and 0 broken, mypy clean over 95 modules, both ratchets at zero
allowances, 209 tests passing.

## New Test Lanes

The template names two lanes xqueue does not have. Both are created by
this plan.

### Workspace and configuration

`tests/workspace/` gains unit and integration cases for:

- marker round-trip, and refusal of an unsupported `schema`;
- resolution precedence across all four steps, each edge tested against
  its immediate neighbour;
- discovery from a nested child directory;
- a same-named `.xqueue/` directory with a missing, malformed, or
  wrong-product marker raising rather than falling back to home;
- idempotent `init`, and `--force` that does not destroy unrelated
  content;
- trackable configuration separated from generated state;
- every adjacent XCFG precedence edge, including the invocation override
  beating the environment layer;
- unknown keys and coercion failures surfacing as `ConfigurationError`;
- a named environment overlay that states only what it changes;
- resolution that does not depend on the test working directory; and
- two clients on different workspaces in one process.

### Parity

`tests/architecture/test_channel_parity.py` asserts the matrix and the
code agree in both directions. It is a structural test, not a behavioral
one; the existing per-operation SDK/CLI parity tests stay as they are.

## Verification Method Per Delta

A gate that has never been observed failing is an assumption. Each new
rule is verified by planting a violation, watching the gate fail, and
reverting — the method that caught the Semgrep scope problem in the
predecessor plan.

| Delta | Planted violation | Expected failure |
| --- | --- | --- |
| Parity matrix | add a facet method | `pytest` names the missing row |
| Parity matrix | add a contract entry | `pytest` names the missing row |
| xcfg isolation | import `xcfg` in an action | `lint-imports` breaks |
| env isolation | `os.environ` in a capability | ratchet exits 1 |
| resolver isolation | import resolver in `jobs` | boundary checker exits 1 |
| packaging | bare install, run `xq` | exit 2 and the hint, not a traceback |

## Risk Register

Each risk is stated with its mitigation. Likelihood and impact are the
author's estimate at plan time.

- **The install command changes** (likely, low impact). Decided with the
  user at Stone 0, documented in four places, and `xq` itself says what
  to install when the extra is missing.
- **XCFG precedence differs from the documented contract** (possible,
  medium impact). Every adjacent edge becomes a test rather than a
  reading of the library's source.
- **Source-rule precedence surprises** (unlikely, medium impact).
  `source_rules_key` stays unset; the feature is not adopted, and the
  template warns that source rules can beat an environment value.
- **Workspace discovery changes which database a command touches**
  (possible, high impact). Absence of a marker keeps today's home
  instance; only an explicit root or a valid marker changes scope; the
  precedence tests cover every step.
- **The `instance/` migration strands local developer state** (possible,
  low impact). The deprecated alias is kept for one release, and
  `workspace init` is idempotent over an existing `instance/`.
- **Deleting `config.py` loses an undocumented behavior** (unlikely,
  medium impact). It is deleted only after the new lane passes, and
  `Settings` keeps the field names of `StaticConfig`, so an existing
  `config.yaml` stays valid in both directions.
- **The plan absorbs template items xqueue has not earned** (possible,
  medium impact). REST, web, and extension tiers are excluded in the
  README by decision rather than by omission.

## Rollback Strategy

Each stone is independently revertible, and no stone leaves a partially
migrated path behind:

- **Stone 1** — documents and one test; delete them.
- **Stone 2** — restore three dependency lines; the import guard is inert
  when the packages are present.
- **Stone 3** — the resolver is additive until its final commit deletes
  the old `resolve_paths` branch; revert that commit to restore the two
  original modes.
- **Stone 4** — restores one deleted module and removes one dependency.
  The `Settings` model keeps the field names of `StaticConfig`, so a
  user's existing `config.yaml` stays valid in both directions.
- **Stone 5** — rules are removable individually.

The user-visible contracts that must not change at any point: the `xq`
command surface, CLI output shapes for all 49 contracts, exit codes, the
SDK's public method signatures, and the on-disk database. Any stone that
would change one of these stops and asks first.

## Definition of Done

The plan is complete when the template's Definition of Done holds for
every applicable item:

- [ ] capabilities named in user vocabulary — already true;
- [ ] typed input, result, and semantic errors per use case — already
      true;
- [ ] domain and action tests without CLI or real infrastructure —
      already true;
- [ ] one public SDK import with explicit lifecycle — already true;
- [ ] validated workspace object, marker version, path ownership, and
      init contract shared by all runtimes — Stone 3;
- [ ] XCFG behind an app-owned adapter with tested precedence — Stone 4;
- [ ] CLI non-interactive, structured, free of business logic — already
      true;
- [ ] local SDK and any remote client named separately — not applicable,
      no remote client;
- [ ] channel parity matrix recording support and omissions — Stone 1;
- [ ] plane map naming state ownership, contracts, and degraded
      behavior — Stone 1;
- [ ] architecture checks forbidding channel, framework, and persistence
      leakage — already true, extended in Stone 5;
- [ ] packaging tests for wheel, `py.typed`, exports, and scripts —
      already true, extended in Stone 2;
- [ ] FastAPI, web client, extension points — out of scope by decision;
- [ ] failure drills — not applicable; no independent plane operation is
      claimed, and the plane map says so explicitly.
