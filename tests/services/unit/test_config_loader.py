from __future__ import annotations

import os
from pathlib import Path

import pytest

from xqueue_libs.services.config import ConfigLoader


def test_load_without_file_returns_home_defaults(tmp_path: Path) -> None:
    loader = ConfigLoader(app_name="xqueue-test", app_author="xqueue-test")
    xqueue_home = Path(os.environ["XQUEUE_HOME"])

    config = loader.load(config_path=tmp_path / "missing.yaml")

    assert config.paths.config_file == tmp_path / "missing.yaml"
    assert config.paths.state_root == xqueue_home
    assert config.paths.runtime_root == xqueue_home / "run"
    assert config.paths.log_root == xqueue_home / "logs"
    assert config.paths.database_path == xqueue_home / "xqueue.db"
    assert config.queue.default_queue == "default"
    assert config.worker.poll_interval_seconds == 1.0
    assert config.worker.retry_delay_seconds == 5


def test_load_from_yaml_overrides_paths_and_defaults(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                f"database_path: {tmp_path / 'data' / 'queue.db'}",
                f"log_root: {tmp_path / 'logs'}",
                f"runtime_root: {tmp_path / 'runtime'}",
                f"state_root: {tmp_path / 'state'}",
                "queue:",
                "  default_queue: agent",
                "worker:",
                "  poll_interval_seconds: 2.5",
                "  default_timeout_seconds: 120",
                "  cancel_grace_period_seconds: 15",
                "  retry_delay_seconds: 9",
                "controller:",
                "  pools:",
                "    agents:",
                "      queues: [agent, priority]",
                "      concurrency: 2",
                "      poll_interval_seconds: 0.5",
                "      lease_seconds: 45",
                "      restart_policy: always",
                "      default_timeout_seconds: 90",
            ]
        )
    )

    loader = ConfigLoader()
    config = loader.load(config_path=config_file)

    assert config.paths.config_file == config_file
    assert config.paths.database_path == tmp_path / "data" / "queue.db"
    assert config.paths.log_root == tmp_path / "logs"
    assert config.paths.runtime_root == tmp_path / "runtime"
    assert config.paths.state_root == tmp_path / "state"
    assert config.queue.default_queue == "agent"
    assert config.worker.poll_interval_seconds == 2.5
    assert config.worker.default_timeout_seconds == 120
    assert config.worker.cancel_grace_period_seconds == 15
    assert config.worker.retry_delay_seconds == 9
    assert config.controller.pools["agents"].queues == ["agent", "priority"]
    assert config.controller.pools["agents"].concurrency == 2
    assert config.controller.pools["agents"].poll_interval_seconds == 0.5
    assert config.controller.pools["agents"].lease_seconds == 45
    assert config.controller.pools["agents"].restart_policy.value == "always"
    assert config.controller.pools["agents"].default_timeout_seconds == 90


def test_workspace_instance_mode_roots_runtime_data_in_repo(tmp_path: Path) -> None:
    loader = ConfigLoader()

    config = loader.load(workspace_root=tmp_path, use_workspace_instance=True)

    assert config.paths.state_root == tmp_path / "instance"
    assert config.paths.runtime_root == tmp_path / "instance" / "run"
    assert config.paths.log_root == tmp_path / "instance" / "logs"
    assert config.paths.database_path == tmp_path / "instance" / "xqueue.db"


def test_workspace_instance_mode_requires_workspace_root() -> None:
    loader = ConfigLoader()

    with pytest.raises(ValueError, match="workspace_root is required"):
        loader.resolve_paths(use_workspace_instance=True)
