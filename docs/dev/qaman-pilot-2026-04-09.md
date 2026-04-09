# qaman Pilot Note

Date: 2026-04-09

## Summary

`xqueue` now has a minimal but credible `qaman` rollout:

- `qa doctor` for shared quality-workflow readiness
- `qa profile run default` for the shared deterministic verification lane
- `qa profile run style` for Ruff-only checks
- `qa profile run architecture` for the Semgrep-backed architecture audit
- `qa progress` for before/current/remaining-work visibility

## Verified lanes

### Default

Current `default` combines:

- `pytest`
- `ruff`

Underlying deterministic test lane:

```sh
uv run pytest tests -x
```

### Style

`ruff` was added as the first extra quality layer because it already ran cleanly
in exploratory mode and therefore added low-risk value.

### Architecture

Semgrep rules were added for already-documented boundaries, including:

- Rich only in the shared output module
- Typer only in CLI shells
- SQLAlchemy not in apps or domain layers
- subprocess use restricted to approved services

## Boundary

- `xq doctor` / `xq health` remain the source of truth for `xqueue` runtime and
  operational health
- `qa doctor` is only about the shared `qaman` setup in this repo

## Current recommendation

Adopt now:

- `pytest`
- `ruff`
- Semgrep architecture audit

Defer:

- `mypy`
- docs QA
