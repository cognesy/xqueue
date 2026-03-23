# Operations

This chapter is derived from the root `SPEC.md`.
`SPEC.md` remains the canonical source of truth.

## Query and Inspection Model

Inspection must work well for both humans and agents.

The system should support filtering by at least:

- job id
- queue
- state
- worker id
- creation time
- availability time

Queue and worker inspection should be first-class operations, not debug tools.

Examples:

```sh
xq jobs list --queue agent --state running --output json
xq workers list --output json
xq queues stats --output json
```

## Health and Recovery

Daily operations require explicit health and recovery commands.

At minimum, the CLI should support:

- `xq health`
- `xq doctor`
- `xq recover stale-leases`
- `xq db check`
- `xq db vacuum`

These commands should help operators and agents answer questions such as:

- is the database healthy?
- are workers heartbeating?
- are there stale leases?
- are queues paused?
- does local state need maintenance?

## Exit Codes

CLI exit codes should be stable and intentional.

At minimum, the implementation should reserve distinct non-zero exit codes for:

- validation error
- not found
- conflict or invalid state transition
- runtime execution error
- timeout or interrupted operation where applicable

This matters for agent automation and shell scripting.

## Packaging and Execution Environment

Daily operations require a clear install and runtime story.

The project should define:

- how `xq` is installed with `uv`
- how platform service units invoke the correct `uv`-managed environment
- whether a small stable wrapper entrypoint script is generated for services

Native service-manager integration must not depend on fragile ad hoc shell
initialization.

## Relationship to xcron

The intended split is:

- `xcron` decides when to run something
- `xq` decides how queued command work is executed and observed

Example:

```sh
xcron -> poll-mailbox -> xq enqueue --queue agent -- "run-agent --task 123"
```

This keeps scheduling separate from queue execution and keeps both tools small.

When background workers should remain continuously available, `xq` should use
native service managers rather than trying to stretch `xcron` into daemon
supervision.
