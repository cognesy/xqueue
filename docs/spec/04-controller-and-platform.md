# Controller And Platform

This chapter is derived from the root `SPEC.md`.
`SPEC.md` remains the canonical source of truth.

## Controller Model

`xq` should support two worker operating modes:

- direct mode
  - the operator runs `xq worker ...` manually
- controller mode
  - a long-lived `xq controller` process supervises one or more worker pools

The controller is not required for the queue to function, but it should be the
standard way to keep worker pools running continuously in the background.

Controller responsibilities:

- load static worker-pool configuration
- launch worker child processes
- restart failed workers according to policy
- expose controller and worker status via CLI
- shut workers down cleanly on stop/restart

The controller should supervise workers. It should not also become a scheduler.

The controller should also support graceful operational modes such as:

- pause intake
- drain workers
- graceful stop
- restart with configuration reload

## Platform Integration

`xq` should follow the same broad integration philosophy as `xcron`:

- keep platform-specific service-management logic behind dedicated services
- generate only explicit managed artifacts
- use deterministic machine-local state paths
- keep ownership boundaries strict

However, the native integration target is different from `xcron`.

`xcron` reconciles one-shot scheduled jobs, so it targets:

- macOS: `launchd`
- Linux: `cron`

`xq` needs a long-lived background controller, so the preferred service-manager
targets should be:

- macOS: `launchd` user agent
- Linux: `systemd --user`

`cron` is not an appropriate primary integration target for the `xq`
controller, because `cron` schedules one-shot commands rather than supervising
long-lived worker daemons.

`systemd` is common on Linux but must not be assumed to exist on every Linux
system.

Therefore the Linux strategy should be:

- primary integration target: `systemd --user`
- mandatory fallback: direct shell mode
- possible later adapter if needed: `OpenRC`

The project should not claim universal Linux daemon-manager support in v1.

### macOS

On macOS, `xq controller install` should generate and manage a `launchd`
LaunchAgent.

Expected approach:

- managed plist in `~/Library/LaunchAgents`
- label prefix such as `dev.xq.controller.`
- `RunAtLoad = true`
- `KeepAlive = true`
- `ProgramArguments` invoking `xq controller run`
- stdout/stderr paths under the managed `xq` state/log root

Lifecycle operations should map to `launchctl`:

- install/bootstrap
- enable
- kickstart or equivalent restart flow
- bootout/uninstall
- status inspection

### Linux

On Linux, `xq controller install` should generate and manage a user-scoped
`systemd` service unit.

Expected approach:

- managed unit file under the user systemd unit directory
- service name such as `xq-controller.service` or a profile-specific variant
- `ExecStart=` invoking `xq controller run`
- `Restart=on-failure` or similar
- working directory and environment set explicitly
- stdout/stderr routed to deterministic managed log files or journald according
  to the chosen policy

Lifecycle operations should map to `systemctl --user`:

- daemon-reload
- enable --now
- start
- stop
- restart
- status
- disable
- remove managed unit

### Fallback behavior

If the native service manager is unavailable or the operator chooses not to use
it, `xq controller run` and `xq worker ...` must still be usable directly from
the shell.

That direct mode is a fallback and a development path. It should not be the
only long-running deployment story.

### Explicit non-goals for v1 platform integration

The following are not required in v1:

- `OpenRC` integration
- `runit` integration
- `s6` integration
- claiming support for all Linux init systems

Those may be added later behind the same service-integration boundary if real
operator demand exists.

## Ownership Model

`xq` must only modify artifacts it owns.

Examples:

- `launchd` labels prefixed with `dev.xq.`
- managed plist files in a known directory
- managed `systemd --user` unit files with a stable naming convention
- generated runtime wrappers or helper scripts in the managed state directory

This follows the same safety rule used in `xcron`: never touch unmanaged native
artifacts.
