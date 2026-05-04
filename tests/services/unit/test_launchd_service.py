from __future__ import annotations

import plistlib
from pathlib import Path

from xqueue_libs.services.launchd import CommandResult, LaunchdService


def test_launchd_service_renders_expected_owned_plist(tmp_path: Path) -> None:
    service = LaunchdService(managed_dir=tmp_path / "LaunchAgents", python_executable="/tmp/venv/bin/python")

    rendered = service.render_plist(
        controller_id="default",
        workspace_root=tmp_path / "repo",
        config_path=tmp_path / "config.yaml",
        log_root=tmp_path / "logs",
        use_workspace_instance=True,
    )
    payload = plistlib.loads(rendered)

    assert payload["Label"] == "dev.xq.controller.default"
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is True
    assert payload["ProgramArguments"][-1] == "--workspace-instance"
    assert payload["ProgramArguments"][:3] == ["/tmp/venv/bin/python", "-m", "xqueue_cli"]
    assert payload["StandardOutPath"].endswith("launchd.stdout.log")
    assert payload["StandardErrorPath"].endswith("launchd.stderr.log")


def test_launchd_service_install_start_status_uninstall_map_to_launchctl(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def runner(command: list[str]) -> CommandResult:
        commands.append(command)
        if command[:2] == ["launchctl", "print"]:
            return CommandResult(returncode=0, stdout="state = running")
        return CommandResult(returncode=0)

    service = LaunchdService(
        managed_dir=tmp_path / "LaunchAgents",
        runner=runner,
        python_executable="/tmp/venv/bin/python",
    )

    install = service.install(
        controller_id="default",
        workspace_root=tmp_path / "repo",
        config_path=tmp_path / "config.yaml",
        log_root=tmp_path / "logs",
        use_workspace_instance=False,
    )
    status = service.status(controller_id="default")
    start = service.start(controller_id="default")
    restart = service.restart(controller_id="default")
    stop = service.stop(controller_id="default")
    uninstall = service.uninstall(controller_id="default")

    assert install.action == "install"
    assert install.service_name == "dev.xq.controller.default"
    assert status.installed is True
    assert status.active is True
    assert start.action == "start"
    assert restart.action == "restart"
    assert stop.action == "stop"
    assert uninstall.action == "uninstall"
    assert commands[0][:2] == ["launchctl", "bootstrap"]
    assert commands[1][:2] == ["launchctl", "enable"]
    assert any(command[:3] == ["launchctl", "kickstart", "-k"] for command in commands)
    assert any(command[:2] == ["launchctl", "print"] for command in commands)
    assert any(command[:2] == ["launchctl", "bootout"] for command in commands)
    assert service.artifact_path("default").exists() is False


def test_launchd_service_rotates_existing_logs_before_lifecycle_start(tmp_path: Path) -> None:
    service = LaunchdService(
        managed_dir=tmp_path / "LaunchAgents",
        runner=lambda command: CommandResult(returncode=0),
        python_executable="/tmp/venv/bin/python",
    )

    service.install(
        controller_id="default",
        workspace_root=tmp_path / "repo",
        config_path=tmp_path / "config.yaml",
        log_root=tmp_path / "logs",
        use_workspace_instance=False,
    )

    stderr_path = tmp_path / "logs" / "controller" / "default" / "launchd.stderr.log"
    stdout_path = tmp_path / "logs" / "controller" / "default" / "launchd.stdout.log"
    stderr_path.write_text("old stderr\n")
    stdout_path.write_text("old stdout\n")

    service.restart(controller_id="default")

    assert not stderr_path.exists()
    assert not stdout_path.exists()
    assert stderr_path.with_name("launchd.stderr.log.previous").read_text() == "old stderr\n"
    assert stdout_path.with_name("launchd.stdout.log.previous").read_text() == "old stdout\n"

    stderr_path.write_text("new stderr\n")
    service.restart(controller_id="default")

    assert stderr_path.with_name("launchd.stderr.log.previous").read_text() == "old stderr\n"
    assert stderr_path.with_name("launchd.stderr.log.previous.1").read_text() == "new stderr\n"
