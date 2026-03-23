# Overview

This chapter is derived from the root `SPEC.md`.
`SPEC.md` remains the canonical source of truth.

## Name

- project name: `xqueue`
- CLI name: `xq`

`xqueue` is a minimal, single-machine, CLI-first durable work queue for running
shell commands.

## Technology Baseline

The initial implementation should use:

- Python
- `uv` for environment and dependency management from day one
- Typer for the CLI surface
- Rich for human-readable text output
- Pydantic for data models
- PyYAML for YAML configuration parsing
- SQLAlchemy for database access
- Alembic for schema migrations
- `platformdirs` for default config, state, runtime, and log paths
- structlog for structured application logging
- pytest for automated testing

Additional implementation guidance:

- `uv` is mandatory, not optional
- project setup, dependency installation, local execution, and test workflows
  should all assume `uv`
- human-readable rendering must be cleanly separated from machine-readable JSON
  output
- database models and API/data models should remain separate concerns
- Rich must only affect `--output text`
- `--output json` must bypass presentation formatting entirely
- YAML is for static configuration, never for mutable queue state
- application logs should be structured and emitted through `structlog`
- prefer standard `subprocess` plus process groups over heavier execution
  machinery
- `psutil` is optional and should only be added if native process-group
  handling proves insufficient

## Context

`xqueue` exists to complement `xcron`.

The intended operating model is:

1. `xcron` runs a periodic command such as a mailbox poller
2. that command decides whether there is work to do
3. if work exists, it enqueues one or more command-execution jobs into `xq`
4. `xq` workers execute those jobs with explicit concurrency control

This system is intentionally local-first and single-machine. It is not intended
to be a distributed queue, a workflow engine, or a general-purpose task
platform.

## Problem Statement

The user needs a lightweight queue with these constraints:

- the queue must be fully operable via CLI
- the jobs are shell commands, not Python functions or serialized callables
- the system runs on one machine
- durability matters
- concurrency control matters
- inspection and cancellation matter
- no GUI or web UI is required or desired

Existing systems often miss one or more of these requirements:

- too heavy operationally
- not truly CLI-first
- tied to application-level function execution
- designed around distributed infrastructure

`xqueue` should solve the narrow local queueing problem with minimal machinery.

## Product Positioning

`xqueue` is:

- a local durable queue for command execution
- a CLI-first operator tool
- a small control plane for one-machine worker management
- a complement to `xcron`

`xqueue` is not:

- a distributed message broker
- a function execution framework
- a workflow engine or DAG runner
- a scheduler
- a replacement for OS process supervision
