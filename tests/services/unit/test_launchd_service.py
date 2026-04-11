from __future__ import annotations

import plistlib
from pathlib import Path

from libs.services.cli_bootstrap import xqueue_repo_root
from libs.services.launchd import CommandResult, LaunchdService


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
    assert "sys.path.insert" in payload["ProgramArguments"][2]
    assert str(xqueue_repo_root()) in payload["ProgramArguments"][2]
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
