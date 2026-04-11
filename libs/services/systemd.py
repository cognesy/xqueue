"""Linux systemd --user integration for managed controller lifecycle."""

from __future__ import annotations

import subprocess
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from libs.domain.models import ManagedControllerInstallView, ManagedControllerStatusView, ServiceManagerKind
from libs.services.cli_bootstrap import xqueue_python_command


@dataclass(frozen=True)
class CommandResult:
    """Minimal command result abstraction."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


class SystemdUserService:
    """Render and manage a user-scoped systemd unit for the controller."""

    def __init__(
        self,
        *,
        managed_dir: Path | None = None,
        runner: Callable[[list[str]], CommandResult] | None = None,
        python_executable: str = "python3",
    ) -> None:
        self._managed_dir = managed_dir or Path.home() / ".config" / "systemd" / "user"
        self._runner = runner or self._run
        self._python_executable = python_executable

    def render_unit(
        self,
        *,
        controller_id: str,
        workspace_root: Path,
        config_path: Path,
        log_root: Path,
        use_workspace_instance: bool,
    ) -> str:
        stdout_path = log_root / "controller" / controller_id / "systemd.stdout.log"
        stderr_path = log_root / "controller" / controller_id / "systemd.stderr.log"
        exec_start = xqueue_python_command(
            self._python_executable,
            "controller",
            "run",
            "--controller-id",
            controller_id,
        )
        if use_workspace_instance:
            exec_start.append("--workspace-instance")

        return "\n".join(
            [
                "[Unit]",
                f"Description=xqueue controller ({controller_id})",
                "",
                "[Service]",
                "Type=simple",
                f"WorkingDirectory={workspace_root}",
                f"Environment=XQUEUE_CONFIG_PATH={config_path}",
                f"ExecStart={shlex.join(exec_start)}",
                "Restart=on-failure",
                f"StandardOutput=append:{stdout_path}",
                f"StandardError=append:{stderr_path}",
                "",
                "[Install]",
                "WantedBy=default.target",
                "",
            ]
        )

    def install(
        self,
        *,
        controller_id: str,
        workspace_root: Path,
        config_path: Path,
        log_root: Path,
        use_workspace_instance: bool,
    ) -> ManagedControllerInstallView:
        artifact_path = self.artifact_path(controller_id)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        (log_root / "controller" / controller_id).mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            self.render_unit(
                controller_id=controller_id,
                workspace_root=workspace_root,
                config_path=config_path,
                log_root=log_root,
                use_workspace_instance=use_workspace_instance,
            )
        )
        self._runner(["systemctl", "--user", "daemon-reload"])
        self._runner(["systemctl", "--user", "enable", self.service_name(controller_id)])
        return ManagedControllerInstallView(
            manager=ServiceManagerKind.SYSTEMD,
            controller_id=controller_id,
            service_name=self.service_name(controller_id),
            artifact_path=str(artifact_path),
            action="install",
        )

    def uninstall(self, *, controller_id: str) -> ManagedControllerInstallView:
        artifact_path = self.artifact_path(controller_id)
        self._runner(["systemctl", "--user", "disable", "--now", self.service_name(controller_id)])
        if artifact_path.exists():
            artifact_path.unlink()
        self._runner(["systemctl", "--user", "daemon-reload"])
        return ManagedControllerInstallView(
            manager=ServiceManagerKind.SYSTEMD,
            controller_id=controller_id,
            service_name=self.service_name(controller_id),
            artifact_path=str(artifact_path),
            action="uninstall",
        )

    def start(self, *, controller_id: str) -> ManagedControllerInstallView:
        self._runner(["systemctl", "--user", "start", self.service_name(controller_id)])
        return self._mutation(controller_id=controller_id, action="start")

    def stop(self, *, controller_id: str) -> ManagedControllerInstallView:
        self._runner(["systemctl", "--user", "stop", self.service_name(controller_id)])
        return self._mutation(controller_id=controller_id, action="stop")

    def restart(self, *, controller_id: str) -> ManagedControllerInstallView:
        self._runner(["systemctl", "--user", "restart", self.service_name(controller_id)])
        return self._mutation(controller_id=controller_id, action="restart")

    def status(self, *, controller_id: str) -> ManagedControllerStatusView:
        artifact_path = self.artifact_path(controller_id)
        load = self._runner(["systemctl", "--user", "is-enabled", self.service_name(controller_id)])
        active = self._runner(["systemctl", "--user", "is-active", self.service_name(controller_id)])
        details = "\n".join(part for part in [load.stdout.strip(), active.stdout.strip(), load.stderr.strip(), active.stderr.strip()] if part)
        return ManagedControllerStatusView(
            manager=ServiceManagerKind.SYSTEMD,
            controller_id=controller_id,
            service_name=self.service_name(controller_id),
            artifact_path=str(artifact_path),
            installed=artifact_path.exists(),
            loaded=load.returncode == 0,
            active=active.returncode == 0,
            details=details or None,
        )

    def service_name(self, controller_id: str) -> str:
        return f"xq-controller-{controller_id}.service"

    def artifact_path(self, controller_id: str) -> Path:
        return self._managed_dir / self.service_name(controller_id)

    def _mutation(self, *, controller_id: str, action: str) -> ManagedControllerInstallView:
        artifact_path = self.artifact_path(controller_id)
        return ManagedControllerInstallView(
            manager=ServiceManagerKind.SYSTEMD,
            controller_id=controller_id,
            service_name=self.service_name(controller_id),
            artifact_path=str(artifact_path),
            action=action,
        )

    def _run(self, command: list[str]) -> CommandResult:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        return CommandResult(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
