from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner
from xqueue.controller.models import ManagedControllerInstallView, ManagedControllerStatusView, ServiceManagerKind
from xqueue.runtime.composition import Runtime
from xqueue_cli.main import app

runner = CliRunner()


def test_controller_status_returns_stopped_json_without_runtime_state(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".xqueue").mkdir(exist_ok=True)

        result = runner.invoke(app, ["controller", "status", "--output", "json", "--workspace-instance"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["item"]["state"] == "stopped"
        assert payload["item"]["controller_id"] == "default"


def test_controller_run_returns_json_with_bounded_supervision_loop(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".xqueue").mkdir(exist_ok=True)

        result = runner.invoke(
            app,
            [
                "controller",
                "run",
                "--max-supervision-loops",
                "1",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["item"]["controller_id"] == "default"
        assert payload["item"]["state"] == "stopped"
        assert payload["item"]["process_id"] is not None
        assert payload["item"]["pools"] == []
        assert Path(".xqueue/run/controller-default.status.json").exists()


def test_controller_pause_resume_drain_restart_stop_return_mutation_json(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)

        pause_result = runner.invoke(app, ["controller", "pause-intake", "--output", "json", "--workspace-instance"])
        resume_result = runner.invoke(app, ["controller", "resume-intake", "--output", "json", "--workspace-instance"])
        drain_result = runner.invoke(app, ["controller", "drain", "--output", "json", "--workspace-instance"])
        restart_result = runner.invoke(app, ["controller", "restart", "--output", "json", "--workspace-instance"])
        stop_result = runner.invoke(app, ["controller", "stop", "--output", "json", "--workspace-instance"])

        assert pause_result.exit_code == 0
        assert resume_result.exit_code == 0
        assert drain_result.exit_code == 0
        assert restart_result.exit_code == 0
        assert stop_result.exit_code == 0

        assert json.loads(pause_result.stdout)["item"]["requested_state"] == "paused"
        assert json.loads(resume_result.stdout)["item"]["requested_state"] == "active"
        assert json.loads(drain_result.stdout)["item"]["requested_state"] == "draining"
        assert json.loads(restart_result.stdout)["item"]["requested_state"] == "restarting"
        stop_payload = json.loads(stop_result.stdout)
        assert stop_payload["item"]["requested_state"] == "stopping"
        assert Path(stop_payload["item"]["control_path"]).exists()


def test_controller_managed_commands_return_json(tmp_path: Path, monkeypatch) -> None:
    class FakeManagedService:
        def install(self, *, controller_id, workspace_root, config_path, log_root, use_workspace_instance):
            return ManagedControllerInstallView(
                manager=ServiceManagerKind.LAUNCHD,
                controller_id=controller_id,
                service_name="dev.xq.controller.default",
                artifact_path=str(workspace_root / "artifact.plist"),
                action="install",
            )

        def uninstall(self, *, controller_id):
            return ManagedControllerInstallView(
                manager=ServiceManagerKind.LAUNCHD,
                controller_id=controller_id,
                service_name="dev.xq.controller.default",
                artifact_path="/tmp/artifact.plist",
                action="uninstall",
            )

        def start(self, *, controller_id):
            return ManagedControllerInstallView(
                manager=ServiceManagerKind.LAUNCHD,
                controller_id=controller_id,
                service_name="dev.xq.controller.default",
                artifact_path="/tmp/artifact.plist",
                action="start",
            )

        def stop(self, *, controller_id):
            return ManagedControllerInstallView(
                manager=ServiceManagerKind.LAUNCHD,
                controller_id=controller_id,
                service_name="dev.xq.controller.default",
                artifact_path="/tmp/artifact.plist",
                action="stop",
            )

        def restart(self, *, controller_id):
            return ManagedControllerInstallView(
                manager=ServiceManagerKind.LAUNCHD,
                controller_id=controller_id,
                service_name="dev.xq.controller.default",
                artifact_path="/tmp/artifact.plist",
                action="restart",
            )

        def status(self, *, controller_id):
            return ManagedControllerStatusView(
                manager=ServiceManagerKind.LAUNCHD,
                controller_id=controller_id,
                service_name="dev.xq.controller.default",
                artifact_path="/tmp/artifact.plist",
                installed=True,
                loaded=True,
                active=True,
                details="running",
            )

    monkeypatch.setattr(Runtime, "managed_controller_service", lambda self, platform=None: FakeManagedService())

    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)

        install = runner.invoke(
            app, ["controller", "install", "--platform", "launchd", "--output", "json", "--workspace-instance"]
        )
        start = runner.invoke(
            app, ["controller", "start", "--platform", "launchd", "--output", "json", "--workspace-instance"]
        )
        status = runner.invoke(
            app, ["controller", "status", "--platform", "launchd", "--output", "json", "--workspace-instance"]
        )
        restart = runner.invoke(
            app, ["controller", "restart", "--platform", "launchd", "--output", "json", "--workspace-instance"]
        )
        stop = runner.invoke(
            app, ["controller", "stop", "--platform", "launchd", "--output", "json", "--workspace-instance"]
        )
        uninstall = runner.invoke(
            app, ["controller", "uninstall", "--platform", "launchd", "--output", "json", "--workspace-instance"]
        )

        assert install.exit_code == 0
        assert start.exit_code == 0
        assert status.exit_code == 0
        assert restart.exit_code == 0
        assert stop.exit_code == 0
        assert uninstall.exit_code == 0

        assert json.loads(install.stdout)["item"]["action"] == "install"
        assert json.loads(start.stdout)["item"]["action"] == "start"
        assert json.loads(status.stdout)["item"]["manager"] == "launchd"
        assert json.loads(restart.stdout)["item"]["action"] == "restart"
        assert json.loads(stop.stdout)["item"]["action"] == "stop"
        assert json.loads(uninstall.stdout)["item"]["action"] == "uninstall"


def test_controller_pool_commands_mutate_workspace_config_idempotently(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".xqueue").mkdir(exist_ok=True)

        ensure = runner.invoke(
            app,
            [
                "controller",
                "pools",
                "ensure",
                "xpm",
                "--queue",
                "xpm",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )
        ensure_again = runner.invoke(
            app,
            [
                "controller",
                "pools",
                "ensure",
                "xpm",
                "--queue",
                "xpm",
                "--output",
                "json",
                "--workspace-instance",
            ],
        )
        listed = runner.invoke(app, ["controller", "pools", "list", "--output", "json", "--workspace-instance"])
        removed = runner.invoke(
            app, ["controller", "pools", "remove", "xpm", "--output", "json", "--workspace-instance"]
        )
        removed_again = runner.invoke(
            app, ["controller", "pools", "remove", "xpm", "--output", "json", "--workspace-instance"]
        )

        assert ensure.exit_code == 0
        assert ensure_again.exit_code == 0
        assert listed.exit_code == 0
        assert removed.exit_code == 0
        assert removed_again.exit_code == 0

        ensure_payload = json.loads(ensure.stdout)
        assert ensure_payload["item"]["action"] == "created"
        assert ensure_payload["item"]["pool"]["queues"] == ["xpm"]
        assert ensure_payload["item"]["restart_required"] is True
        assert ensure_payload["item"]["restart_command"] == "xq controller restart"
        assert json.loads(ensure_again.stdout)["item"]["action"] == "noop"
        assert json.loads(listed.stdout)["items"][0]["name"] == "xpm"
        assert json.loads(removed.stdout)["item"]["action"] == "removed"
        assert json.loads(removed_again.stdout)["item"]["action"] == "noop"
