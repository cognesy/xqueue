"""macOS launchd integration for managed controller lifecycle."""

from __future__ import annotations

import plistlib
import subprocess
from dataclasses import dataclass
from os import getuid
from pathlib import Path
from typing import Callable

from xqueue_libs.domain.models import ManagedControllerInstallView, ManagedControllerStatusView, ServiceManagerKind
from xqueue_libs.services.cli_bootstrap import xqueue_python_command

SERVICE_LOG_KEYS = ("StandardOutPath", "StandardErrorPath")


@dataclass(frozen=True)
class CommandResult:
    """Minimal command result abstraction."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


class LaunchdService:
    """Render and manage a launchd LaunchAgent for the controller."""

    def __init__(
        self,
        *,
        managed_dir: Path | None = None,
        runner: Callable[[list[str]], CommandResult] | None = None,
        python_executable: str = "python3",
    ) -> None:
        self._managed_dir = managed_dir or Path.home() / "Library" / "LaunchAgents"
        self._runner = runner or self._run
        self._python_executable = python_executable

    def render_plist(
        self,
        *,
        controller_id: str,
        workspace_root: Path,
        config_path: Path,
        log_root: Path,
        use_workspace_instance: bool,
    ) -> bytes:
        label = self.service_name(controller_id)
        stdout_path = log_root / "controller" / controller_id / "launchd.stdout.log"
        stderr_path = log_root / "controller" / controller_id / "launchd.stderr.log"
        program_arguments = xqueue_python_command(
            self._python_executable,
            "controller",
            "run",
            "--controller-id",
            controller_id,
        )
        if use_workspace_instance:
            program_arguments.append("--workspace-instance")

        payload = {
            "Label": label,
            "ProgramArguments": program_arguments,
            "WorkingDirectory": str(workspace_root),
            "RunAtLoad": True,
            "KeepAlive": True,
            "StandardOutPath": str(stdout_path),
            "StandardErrorPath": str(stderr_path),
            "EnvironmentVariables": {
                "XQUEUE_CONFIG_PATH": str(config_path),
            },
        }
        return plistlib.dumps(payload)

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
        artifact_path.write_bytes(
            self.render_plist(
                controller_id=controller_id,
                workspace_root=workspace_root,
                config_path=config_path,
                log_root=log_root,
                use_workspace_instance=use_workspace_instance,
            )
        )
        self._rotate_existing_service_logs(controller_id)
        self._runner(["launchctl", "bootstrap", self._domain_target(), str(artifact_path)])
        self._runner(["launchctl", "enable", f"{self._domain_target()}/{self.service_name(controller_id)}"])
        return ManagedControllerInstallView(
            manager=ServiceManagerKind.LAUNCHD,
            controller_id=controller_id,
            service_name=self.service_name(controller_id),
            artifact_path=str(artifact_path),
            action="install",
        )

    def uninstall(self, *, controller_id: str) -> ManagedControllerInstallView:
        artifact_path = self.artifact_path(controller_id)
        self._runner(["launchctl", "bootout", self._domain_target(), str(artifact_path)])
        if artifact_path.exists():
            artifact_path.unlink()
        return ManagedControllerInstallView(
            manager=ServiceManagerKind.LAUNCHD,
            controller_id=controller_id,
            service_name=self.service_name(controller_id),
            artifact_path=str(artifact_path),
            action="uninstall",
        )

    def start(self, *, controller_id: str) -> ManagedControllerInstallView:
        artifact_path = self.artifact_path(controller_id)
        self._rotate_existing_service_logs(controller_id)
        self._runner(["launchctl", "bootstrap", self._domain_target(), str(artifact_path)])
        self._runner(["launchctl", "enable", f"{self._domain_target()}/{self.service_name(controller_id)}"])
        self._runner(["launchctl", "kickstart", "-k", f"{self._domain_target()}/{self.service_name(controller_id)}"])
        return self._mutation(controller_id=controller_id, action="start")

    def stop(self, *, controller_id: str) -> ManagedControllerInstallView:
        self._runner(["launchctl", "bootout", self._domain_target(), self.service_name(controller_id)])
        return self._mutation(controller_id=controller_id, action="stop")

    def restart(self, *, controller_id: str) -> ManagedControllerInstallView:
        self._rotate_existing_service_logs(controller_id)
        self._runner(["launchctl", "kickstart", "-k", f"{self._domain_target()}/{self.service_name(controller_id)}"])
        return self._mutation(controller_id=controller_id, action="restart")

    def status(self, *, controller_id: str) -> ManagedControllerStatusView:
        artifact_path = self.artifact_path(controller_id)
        result = self._runner(["launchctl", "print", f"{self._domain_target()}/{self.service_name(controller_id)}"])
        return ManagedControllerStatusView(
            manager=ServiceManagerKind.LAUNCHD,
            controller_id=controller_id,
            service_name=self.service_name(controller_id),
            artifact_path=str(artifact_path),
            installed=artifact_path.exists(),
            loaded=result.returncode == 0,
            active=result.returncode == 0,
            details=result.stdout or result.stderr or None,
        )

    def service_name(self, controller_id: str) -> str:
        return f"dev.xq.controller.{controller_id}"

    def artifact_path(self, controller_id: str) -> Path:
        return self._managed_dir / f"{self.service_name(controller_id)}.plist"

    def _domain_target(self) -> str:
        return f"gui/{getuid()}"

    def _mutation(self, *, controller_id: str, action: str) -> ManagedControllerInstallView:
        artifact_path = self.artifact_path(controller_id)
        return ManagedControllerInstallView(
            manager=ServiceManagerKind.LAUNCHD,
            controller_id=controller_id,
            service_name=self.service_name(controller_id),
            artifact_path=str(artifact_path),
            action=action,
        )

    def _rotate_existing_service_logs(self, controller_id: str) -> None:
        for path in self._service_log_paths(controller_id):
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.stat().st_size == 0:
                continue

            path.replace(self._next_rotated_log_path(path))

    def _service_log_paths(self, controller_id: str) -> list[Path]:
        artifact_path = self.artifact_path(controller_id)
        if not artifact_path.exists():
            return []

        payload = plistlib.loads(artifact_path.read_bytes())
        return [Path(payload[key]) for key in SERVICE_LOG_KEYS if isinstance(payload.get(key), str)]

    def _next_rotated_log_path(self, path: Path) -> Path:
        rotated_path = path.with_name(f"{path.name}.previous")
        if not rotated_path.exists():
            return rotated_path

        index = 1
        while True:
            candidate = path.with_name(f"{path.name}.previous.{index}")
            if not candidate.exists():
                return candidate
            index += 1

    def _run(self, command: list[str]) -> CommandResult:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        return CommandResult(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
