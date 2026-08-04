# Channel Parity

Which capability operation each channel exposes, and why anything is
absent. xqueue has two channels: the Python SDK (`from xqueue import
Xqueue`) and the CLI (`xq`). REST and web are absent by decision, not by
omission, so they have no columns here.

`tests/architecture/test_channel_parity.py` parses both tables below and
fails when they stop matching the code. A new facet method or a new
command contract cannot ship without a row.

The SDK is the complete surface: every operation is one public method on
one facet, and the plane of each is stated once in
[`plane-map.md`](plane-map.md) rather than repeated here.

## CLI Contracts

One row per name in `COMMAND_CONTRACTS` (`apps/cli/axi_contracts.py`).
The operation is the SDK method the command calls to do its work.

| Contract | Operation |
| --- | --- |
| `config.show` | `workspace.config` |
| `controller.drain` | `controller.request_state` |
| `controller.install` | `controller.install` |
| `controller.pause-intake` | `controller.request_state` |
| `controller.pools.ensure` | `controller.ensure_pool` |
| `controller.pools.list` | `controller.list_pools` |
| `controller.pools.remove` | `controller.remove_pool` |
| `controller.restart` | `controller.request_state` |
| `controller.resume-intake` | `controller.request_state` |
| `controller.run` | `controller.run` |
| `controller.start` | `controller.managed_lifecycle` |
| `controller.status` | `controller.status` |
| `controller.stop` | `controller.request_state` |
| `controller.uninstall` | `controller.uninstall` |
| `db.check` | `maintenance.check_database` |
| `db.cleanup-retention` | `maintenance.cleanup_retention` |
| `db.reset-workspace-instance` | `workspace.reset_instance` |
| `db.vacuum` | `maintenance.vacuum_database` |
| `doctor` | `maintenance.doctor` |
| `enqueue` | `jobs.enqueue` |
| `error` | — |
| `health` | `maintenance.health` |
| `home` | `maintenance.home` |
| `hooks.install` | `workspace.install_hooks` |
| `hooks.session-end` | `workspace.capture_session_end` |
| `hooks.status` | `workspace.hook_status` |
| `jobs.cancel` | `jobs.cancel` |
| `jobs.delete` | `jobs.delete` |
| `jobs.list` | `jobs.list` |
| `jobs.pane` | `jobs.pane` |
| `jobs.prune` | `jobs.prune` |
| `jobs.purge` | `queues.purge` |
| `jobs.retry` | `jobs.retry` |
| `jobs.show` | `jobs.show` |
| `jobs.tail` | `jobs.tail` |
| `metrics.reset` | `maintenance.reset_metrics` |
| `metrics.show` | `maintenance.metrics` |
| `queues.list` | `queues.list` |
| `queues.pause` | `queues.pause` |
| `queues.resume` | `queues.resume` |
| `queues.stats` | `queues.stats` |
| `recover.stale-leases` | `maintenance.recover_stale_leases` |
| `worker` | `workers.run` |
| `worker.run` | `workers.run` |
| `workers.drain` | `workers.set_state` |
| `workers.list` | `workers.list` |
| `workers.pause` | `workers.set_state` |
| `workers.resume` | `workers.set_state` |
| `workers.stop` | `workers.set_state` |
| `workspace.init` | `workspace.init` |

### Rows that are not one-to-one

- `error` names no operation. It is the failure envelope every command
  falls back to (`apps/cli/output.py:286`), not a capability call.
- `worker` and `worker.run` are the same operation reached two ways:
  `xq worker` with no subcommand, and `xq worker run`. The bare form is
  kept because agent hooks and launchd units invoke it.
- The four `workers.*` state commands are one operation, `set_state`,
  with the target state bound at registration
  (`apps/cli/commands/workers.py:60`). The CLI, not the capability, owns
  the four verbs.
- `controller.stop` and `controller.restart` dispatch on `--platform`:
  with it they call `managed_lifecycle` to act on launchd or systemd,
  without it they request a state through the database. The table names
  the default path; `managed_lifecycle` has its own row under
  `controller.start`, so it is documented either way.
- `controller.drain` and `controller.pause-intake` differ in the state
  requested, not in the method called.
- `worker` also reads `workspace.config` for its defaults
  (`apps/cli/commands/worker.py:75`) before running. That is a read on
  the way to the operation, not a second exposed operation.

## Operations the CLI Does Not Expose

| Operation | Why not |
| --- | --- |
| `workers.claim` | For embedders driving their own poll loop |
| `workers.register` | A step inside `workers.run`, not an operator act |
| `workers.running_commands` | Read by `maintenance.doctor`; no command |

`workers.claim` is the deliberate asymmetry: an embedder that wants to
own its own loop needs to claim without running, while an operator has
no use for a claimed job that nothing executes. The CLI exposes only the
composed `worker run`.

`workers.register` and `workers.running_commands` are not policy
decisions so much as the absence of a use case. If one appears, the row
moves to the table above and the contract is added; the test enforces
that the two stay in step.
