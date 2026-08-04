from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect
from xqueue.workspace.instance import WorkspaceInstanceService
from xqueue.workspace.models import RuntimePaths


def test_reset_removes_runtime_artifacts_and_preserves_config(tmp_path: Path) -> None:
    state_root = tmp_path / ".xqueue"
    runtime_root = state_root / "run"
    log_root = state_root / "logs"
    config_file = state_root / "config.yaml"
    database_path = state_root / "xqueue.db"

    runtime_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    config_file.write_text("queue:\n  default_queue: default\n")
    database_path.write_text("db\n")
    (runtime_root / "worker.pid").write_text("1\n")
    (log_root / "worker.log").write_text("log\n")

    result = WorkspaceInstanceService().reset(
        paths=RuntimePaths(
            config_file=config_file,
            state_root=state_root,
            runtime_root=runtime_root,
            log_root=log_root,
            database_path=database_path,
        )
    )

    assert result.config_file == str(config_file)
    assert config_file.exists()
    assert database_path.exists()
    assert runtime_root.exists()
    assert log_root.exists()
    assert list(runtime_root.iterdir()) == []
    assert list(log_root.iterdir()) == []

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    assert {"jobs", "attempts", "workers", "events", "queues"} <= set(inspector.get_table_names())
