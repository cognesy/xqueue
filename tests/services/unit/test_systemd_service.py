from __future__ import annotations

from pathlib import Path

from libs.services.cli_bootstrap import xqueue_repo_root
from libs.services.systemd import CommandResult, SystemdUserService


def test_systemd_service_renders_expected_owned_unit(tmp_path: Path) -> None:
    service = SystemdUserService(managed_dir=tmp_path / "systemd" / "user", python_executable="/tmp/venv/bin/python")

    rendered = service.render_unit(
        controller_id="default",
        workspace_root=tmp_path / "repo",
        config_path=tmp_path / "config.yaml",
        log_root=tmp_path / "logs",
        use_workspace_instance=True,
    )

    assert "Description=xqueue controller (default)" in rendered
    assert "ExecStart=/tmp/venv/bin/python -c" in rendered
    assert "sys.path.insert" in rendered
    assert str(xqueue_repo_root()) in rendered
    assert "controller run --controller-id default --workspace-instance" in rendered
    assert "Restart=on-failure" in rendered
    assert "StandardOutput=append:" in rendered
    assert "WantedBy=default.target" in rendered


def test_systemd_service_install_start_status_uninstall_map_to_systemctl(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def runner(command: list[str]) -> CommandResult:
        commands.append(command)
        if command[:3] == ["systemctl", "--user", "is-enabled"]:
            return CommandResult(returncode=0, stdout="enabled\n")
        if command[:3] == ["systemctl", "--user", "is-active"]:
            return CommandResult(returncode=0, stdout="active\n")
        return CommandResult(returncode=0)

    service = SystemdUserService(
        managed_dir=tmp_path / "systemd" / "user",
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
    assert install.service_name == "xq-controller-default.service"
    assert status.installed is True
    assert status.loaded is True
    assert status.active is True
    assert start.action == "start"
    assert restart.action == "restart"
    assert stop.action == "stop"
    assert uninstall.action == "uninstall"
    assert commands[0] == ["systemctl", "--user", "daemon-reload"]
    assert commands[1] == ["systemctl", "--user", "enable", "xq-controller-default.service"]
    assert any(command[:3] == ["systemctl", "--user", "start"] for command in commands)
    assert any(command[:3] == ["systemctl", "--user", "restart"] for command in commands)
    assert any(command[:3] == ["systemctl", "--user", "stop"] for command in commands)
    assert any(command[:3] == ["systemctl", "--user", "disable"] for command in commands)
    assert service.artifact_path("default").exists() is False
