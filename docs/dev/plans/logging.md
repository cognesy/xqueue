# Logging Configuration Plan

## Goal

Make `xqueue`'s existing `structlog` setup configurable through a checked-in logging configuration file and fix service-manager behavior so controller logs prove the worker pipeline is actually running.

## Current State

`xqueue` already depends on `structlog` and has `libs/services/logging.py`.

It logs action lifecycle events, but the configuration is code-only:

- level defaults to `INFO`
- format is JSON
- destination is stderr

Operational issue observed during `xpm` setup: the installed launchd controller used the `xpm` working directory and imported `apps.cli.main` from the wrong repo, producing repeated stderr errors:

```text
No such command 'controller'.
```

## Target Configuration

Add a config file, proposed path:

```text
resources/logging/default.yaml
```

Expected shape:

```yaml
version: 1
logger: xqueue
destination: stderr
format: json
level: INFO
timestamp: iso
events:
  actions: true
  workers: true
  controller: true
  jobs: true
  subprocesses: true
fields:
  include:
    - event
    - level
    - timestamp
    - action
    - queue
    - job_id
    - worker_id
    - controller_id
    - attempt_number
    - duration_ms
    - returncode
  redact:
    - token
    - secret
    - credential
```

Environment overrides:

- `XQUEUE_LOG_LEVEL`
- `XQUEUE_LOG_FORMAT`

## Approach

1. Add a typed logging config loader and route `configure_logging()` through it.
2. Preserve stderr-only logging and JSON defaults for service-manager logs.
3. Fix managed launchd/systemd controller command generation so it runs the xqueue CLI from the xqueue repo/module path, not whatever project directory invoked installation.
4. Add tests for generated service command arguments and logging config behavior.
5. Reinstall/restart the local launchd controller after the code fix.

## Task Breakdown

1. Add `resources/logging/default.yaml` and logging config loader.
2. Update `libs/services/logging.py` for file config and env overrides.
3. Fix launchd/systemd controller execution context.
4. Add regression tests for the controller import/working-directory bug.
5. Verify controller service starts, writes valid structlog entries, and workers appear in `xq workers list`.
6. Document log locations and operation commands.

## Risks

- Worker logs and job attempt stdout/stderr are different artifacts. Keep application logs under controller/worker service logs and job attempt output under job log paths.
- Commands may contain secrets. Redact env and avoid logging full command strings above DEBUG where possible.

## Open Questions

- Should job command strings be logged at INFO, DEBUG, or only persisted in job records?
- Should controller service logs include the effective config hash at startup?
