# CLI And Config

This chapter is derived from the root `SPEC.md`.
`SPEC.md` remains the canonical source of truth.

## CLI Requirements

The CLI is the primary interface, not a thin helper over a library.

Every important operation must be available from `xq`.

### Minimum command surface

```sh
xq enqueue --queue agent -- "check-mailbox --agent writer-1"
xq worker --queue agent --concurrency 4
xq jobs list
xq jobs list --state running
xq jobs show <job-id>
xq jobs cancel <job-id>
xq jobs retry <job-id>
xq jobs delete <job-id>
xq jobs tail <job-id>
xq jobs purge --queue <queue>
xq queues list
xq queues stats
xq queues pause <queue>
xq queues resume <queue>
xq workers list
xq workers stop <worker-id>
xq workers pause <worker-id>
xq workers resume <worker-id>
xq workers drain <worker-id>
xq config show
xq controller run
xq controller install
xq controller uninstall
xq controller start
xq controller stop
xq controller restart
xq controller status
xq health
xq doctor
xq recover stale-leases
xq db check
xq db vacuum
```

### CLI principles

- human-readable default output
- structured output is a first-class interface, not a debug feature
- every operator-facing command should support `-o` / `--output`
- the supported formats should be `toon`, `json`, `jsonl`, and `text`
- `--output json` must be stable enough for automation via tools such as `jq`
- non-interactive by default
- stable exit codes
- explicit filtering and sorting

### Output contract

`xq` is intended to be operated by both humans and agents.

Because of that, machine-readable output must be part of the primary CLI design.

Commands that return data or mutation results should support:

```sh
-o toon
-o json
-o jsonl
-o text
```

Guidelines:

- `toon` is the default machine-friendly format
- `json` is optimized for automation
- `jsonl` is optimized for item streaming
- `text` is optimized for humans
- `json` output should avoid presentation-only fields
- `json` output should use stable top-level shapes per command
- error output should remain structured where practical
- field naming should remain stable once released
- JSON output should be easy to compose with `jq`
- `--fields` should allow narrower payloads when appropriate

Suggested JSON conventions:

- list commands return `{ "items": [...] }`
- detail commands return `{ "item": { ... } }`
- successful mutations return `{ "ok": true, "item": { ... } }`
- command collections may include `"meta"` for pagination or summary counts
- failures should return `{ "ok": false, "error": { ... } }` when practical

Suggested error shape:

```json
{
  "ok": false,
  "error": {
    "code": "not_found",
    "message": "job not found",
    "details": {}
  }
}
```

Examples:

```sh
xq jobs list --state queued -o json | jq
xq jobs show <job-id> -o json | jq
xq jobs cancel <job-id> -o json | jq
xq queues stats -o json | jq
```

## Configuration Model

Configuration should be optional and minimal.

The queue must remain operable without a configuration file when flags and
defaults are sufficient.

If a config file is used, YAML is the source format.

Configuration should cover static settings such as:

- database path
- log root
- runtime root
- default queue
- worker polling settings
- default timeout values
- cancel grace period

Configuration should not contain mutable queue state.

The CLI should expose:

```sh
xq -o json config show
```

Controller configuration should be static YAML, not mutable runtime state.

It should support named worker pools with fields such as:

- pool name
- queues served
- concurrency
- polling settings
- restart policy
- default timeout overrides

This configuration should be readable by both direct controller invocation and
platform service integration.

## Filesystem Layout

Default paths should be determined via `platformdirs`.

At minimum, the system should have stable locations for:

- config file
- SQLite database
- stdout/stderr logs
- pid or runtime files if needed

The implementation should not require operators to invent these paths manually
for normal use.
