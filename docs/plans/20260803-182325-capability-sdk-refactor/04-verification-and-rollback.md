# Verification and Rollback

## Invariants Across Every Stone

Every stone must preserve:

- all current commands, options, defaults, and stable exit codes;
- TOON as the default output format;
- JSON, JSONL, text, TOON, and tmux payload semantics;
- list/show/mutation top-level CLI shapes;
- SQLite schema and Alembic migration history unless a stone explicitly and
  separately justifies a schema change;
- attempt and event history;
- atomic claim and at-least-once lease behavior;
- retries, delay, timeout, cancellation, and stale recovery;
- process-group termination correctness;
- stdout/stderr files outside SQLite;
- direct worker and controller operation;
- launchd/systemd ownership rules; and
- workspace and default `~/.xqueue` path behavior.

No stone is accepted on unit tests alone.

## Gate Matrix

| Gate | Every stone | Capability cutover | Final |
| --- | :---: | :---: | :---: |
| Ruff format/lint, once configured | yes | yes | yes |
| Architecture/import contracts | yes | yes | yes |
| Focused capability unit tests | yes | yes | yes |
| Full pytest suite | yes | yes | yes |
| CLI help and exit-code contract | yes | yes | yes |
| JSON/JSONL/TOON/text golden contract | yes | yes | yes |
| SDK/CLI typed parity | when SDK-touched | yes | yes |
| Atomic claim and lease tests | worker-related | worker-related | yes |
| Timeout/cancel/process-group tests | worker-related | worker-related | yes |
| Wheel/sdist clean install | package-touched | yes | yes |
| Current xqa `doctor` | yes | yes | yes |
| Current xqa `mechanism verify` | yes | yes | yes |
| Native Ruff gate | yes | yes | yes |
| Native Semgrep/import-contract gate | yes | yes | yes |

If mypy is added, start strict on new `xqueue.sdk`, capability model, port, and
action packages. Do not claim repository-wide strict typing by adding a broad
ignore list. Expand coverage stone by stone.

## Characterization Fixtures

Before changing structure, capture representative cases for:

- root help and each command-group help;
- empty, populated, and invalid list/show/mutation responses;
- errors for validation, not found, conflict, timeout, and execution failure;
- enqueue plus successful, failed, retried, timed-out, and canceled jobs;
- queue pause/resume and purge;
- worker list/state and stale recovery;
- controller status and managed artifact rendering;
- health, doctor, DB check, metrics, hooks, and home degradation; and
- field projection/full-output interactions for every machine format.

Prefer decoded semantic comparisons for machine formats. Use exact text
snapshots only where human layout is itself the contract.

## Architecture Test Requirements

The enforcer must reject synthetic examples of:

- CLI importing SQLAlchemy or an adapter;
- CLI importing a private capability action or service;
- one capability importing another capability's private module;
- adapters importing CLI or SDK;
- core importing Typer or Rich outside a permitted channel;
- pure capability models importing infrastructure;
- ORM objects crossing a public action or SDK boundary;
- global `xqueue.actions`, `xqueue.services`, `xqueue.domain`, or
  `xqueue.infra` packages reappearing after removal; and
- `xqueue` import eagerly loading channel or platform modules.

Tests must also include legal fixtures so prefix matching and relative imports
do not produce false positives.

## Packaging Verification

Run clean-artifact checks from temporary directories, not the source checkout:

1. build wheel and sdist;
2. inspect archive contents for `py.typed`, migrations, logging config, schemas,
   and agent skills;
3. install the wheel without editable paths;
4. import the exact public surface and inspect `__all__`;
5. assert channel and optional platform modules are not eagerly imported;
6. initialize a temporary workspace;
7. enqueue and run a real shell command through the SDK;
8. inspect the same job through CLI JSON and compare decoded domain fields; and
9. repeat the import and smoke from the sdist-built wheel.

## Rollback Rules

- One stone should be one focused commit or a very small dependency-ordered
  series linked to one Beads task.
- Do not mix capability movement with behavior changes unless the behavior
  change is the task's explicit contract.
- Keep the old and new paths together only inside one active stone; delete the
  replaced path before closing it.
- If parity fails, revert the current stone or shrink it. Do not add a permanent
  dual-write or fallback path.
- Database migrations are out of scope by default. If one becomes necessary,
  create a separate task with forward/backward compatibility evidence.
- Record red bets and changed decisions in `STONE-LOG.md` and the Beads issue.

## Completion Audit

Before closing the epic, verify from the live tree and built artifacts:

- CLI has zero imports from adapters, SQLAlchemy, or private capability code;
- no global technical-layer packages remain;
- every operator use case has one canonical typed action;
- every CLI operation and every SDK method converge on that action;
- every public result is free of ORM and CLI envelope types;
- root package exports are intentional and tested;
- no extension/workspace/process-protocol abstraction was introduced;
- no temporary compatibility shim or duplicated path remains;
- docs match the actual import graph and lifecycle behavior;
- all Beads child tasks and acceptance criteria are complete; and
- Git and Beads synchronization are clean.
