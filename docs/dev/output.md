# Output Architecture

## Status

- Date: 2026-04-10
- Status: Implemented

## Purpose

Describe the current xqueue CLI output boundary after the AXI refactor.

`xq` now has:

- TOON as the default stdout format
- `-o` / `--output` with `toon`, `json`, `jsonl`, and `text`
- a contract-backed `Output` object for command rendering
- structured errors on stdout
- content-first bare `xq`
- repo-local Claude Code and Codex session hooks

## Current Entry Points

Primary files:

- [output.py](/Users/ddebowczyk/projects/xqueue/apps/cli/output.py)
- [runtime.py](/Users/ddebowczyk/projects/xqueue/apps/cli/runtime.py)
- [axi_contracts.py](/Users/ddebowczyk/projects/xqueue/libs/services/axi_contracts.py)
- [toon_renderer.py](/Users/ddebowczyk/projects/xqueue/libs/services/toon_renderer.py)
- [responses.py](/Users/ddebowczyk/projects/xqueue/libs/domain/responses.py)
- [main.py](/Users/ddebowczyk/projects/xqueue/apps/cli/main.py)

## Format Contract

Top-level callback options:

- `-o`, `--output`
- `--fields`
- `--full`

Supported formats:

- `toon`: default machine-friendly format
- `json`: stable structured envelope for automation
- `jsonl`: one JSON row per list item when available
- `text`: human-readable Rich/Pretty path

Rules:

- machine-readable payloads are written to `stdout`
- application logs stay on `stderr`
- Rich is only used for `text`
- JSON must never depend on Rich formatting

## Output Object

Commands now use a pre-configured output surface:

```python
out = Output(ctx, "jobs.list", output)
run_action(lambda: action(filters), out=out)
```

Key behavior:

- resolves the active output format from the local option or parent context
- loads the command contract by name
- validates `--fields` against the contract
- renders responses without commands needing format-specific logic
- renders structured error payloads and raises `typer.Exit`

Useful methods:

- `print(response)`
- `render(response)`
- `error(message, code=..., details=..., exit_code=...)`

Useful properties:

- `fmt`
- `full`
- `contract`
- `requested_fields`

## Command Contracts

Every operator-facing command has a contract in
[axi_contracts.py](/Users/ddebowczyk/projects/xqueue/libs/services/axi_contracts.py).

Contracts are derived from response and nested row/detail models, not manually
duplicated field lists. They define:

- top-level allowed fields
- nested item/list fields
- default fields for TOON output
- validation for `--fields`

Examples:

- `jobs.list`
- `jobs.show`
- `queues.stats`
- `worker`
- `hooks.status`
- `home`
- `error`

## Response Shapes

Stable structured envelopes remain:

- list commands: `{ "items": [...] }`
- detail commands: `{ "item": { ... } }`
- mutations: `{ "ok": true, "item": { ... } }`
- errors: `{ "ok": false, "error": { ... } }`

The common rendering protocol is `PayloadConvertible`:

- `to_payload()`
- `jsonl_items()`

`ListResponse` overrides `jsonl_items()` so JSONL output can stream rows
without guessing by key names.

## Error Handling

`run_action()` is now a thin wrapper over `Output`:

- execute the action
- `out.print(result)` on success
- `out.error(...)` on `XqueueError`

Errors always render through the `error` contract so TOON/JSON output stays
structured even if the active command contract would otherwise filter fields.

## Home View

Bare `xq` now renders live workspace state instead of help text.

The home payload includes:

- executable path
- description
- queue summaries
- aggregate job counts by state
- active worker summaries
- a few next-step hints

Implementation lives in
[home.py](/Users/ddebowczyk/projects/xqueue/apps/cli/home.py).

## Session Hooks

Repo-local hooks are managed through:

- `xq hooks install`
- `xq hooks status`
- `xq hooks session-start`
- `xq hooks session-end`

Implementation lives in
[session_hooks.py](/Users/ddebowczyk/projects/xqueue/libs/services/session_hooks.py).

Behavior:

- installs or repairs `.claude/settings.json`
- installs or repairs `.codex/hooks.json`
- ensures `.codex/config.toml` has `codex_hooks = true`
- uses the absolute executable path
- keeps session-start output aligned with the home view

## Current Verification

The current output stack is covered by:

- [test_output_axi.py](/Users/ddebowczyk/projects/xqueue/tests/cli/unit/test_output_axi.py)
- [test_axi_contracts.py](/Users/ddebowczyk/projects/xqueue/tests/cli/unit/test_axi_contracts.py)
- [test_toon_renderer.py](/Users/ddebowczyk/projects/xqueue/tests/services/unit/test_toon_renderer.py)
- [test_toon_output_contract.py](/Users/ddebowczyk/projects/xqueue/tests/cli/regression/test_toon_output_contract.py)
- [test_json_output_contract.py](/Users/ddebowczyk/projects/xqueue/tests/cli/regression/test_json_output_contract.py)
- [test_home_and_hooks.py](/Users/ddebowczyk/projects/xqueue/tests/cli/unit/test_home_and_hooks.py)
- [test_session_hooks.py](/Users/ddebowczyk/projects/xqueue/tests/services/unit/test_session_hooks.py)

## Operator Examples

```sh
uv run xq
uv run xq jobs list
uv run xq -o json queues list
uv run xq --fields id,state jobs list
uv run xq hooks install
uv run xq hooks status -o json
```
