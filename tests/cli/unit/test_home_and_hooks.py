from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from toon import decode
from typer.testing import CliRunner
from xqueue import Xqueue
from xqueue.adapters.sqlite.database import create_session_factory, create_sqlite_engine
from xqueue.adapters.sqlite.models import Base, JobModel, WorkerModel
from xqueue.adapters.sqlite.session import SessionManager
from xqueue.workspace.marker import build_marker, write_marker
from xqueue_cli.main import app

runner = CliRunner()


def _seed_home_database(database_path: Path) -> None:
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 4, 10, 20, 0, tzinfo=UTC)

    with SessionManager(session_factory).transaction() as session:
        session.add(
            WorkerModel(
                id="worker-home",
                state="active",
                queues=["agent"],
                heartbeat_at=now,
                started_at=now,
            )
        )
        session.add(
            JobModel(
                id="job-home",
                queue="agent",
                command="echo home",
                shell=True,
                priority=10,
                created_at=now,
                available_at=now,
                state="succeeded",
                attempt_count=1,
                max_attempts=1,
            )
        )

    engine.dispose()


def test_bare_xq_shows_content_first_home_view(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # A marker, not just the directory: discovery is what finds this
        # workspace, and discovery only stops at a directory that declares
        # itself one.
        workspace_dir = Path(".xqueue")
        write_marker(workspace_dir, build_marker("test"))
        _seed_home_database(workspace_dir / "xqueue.db")

        result = runner.invoke(app, [])

        assert result.exit_code == 0
        assert "description:" in result.stdout
        assert "queues[1" in result.stdout
        assert "jobs[6" in result.stdout
        assert "workers[1" in result.stdout


def test_bare_xq_without_a_state_store_renders_the_degraded_view(tmp_path: Path) -> None:
    """A workspace with no database yet is an expected state, not a failure."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, [])

        assert result.exit_code == 0
        assert "queues[0]" in result.stdout
        assert "Run `xq db check` to inspect the current state store" in result.stdout


def test_home_does_not_swallow_unexpected_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only a missing store degrades; a bug must not render as a healthy empty view."""

    def _boom(self: object) -> list[object]:
        raise RuntimeError("worker listing is broken")

    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        _seed_home_database(instance / "xqueue.db")

        with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as client:
            monkeypatch.setattr(type(client._runtime.worker_actions.list), "__call__", _boom)

            with pytest.raises(RuntimeError, match="worker listing is broken"):
                client.maintenance.home()


def test_hooks_install_and_status_commands_work_in_repo_root(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        install = runner.invoke(app, ["hooks", "install", "-o", "json"])

        assert install.exit_code == 0
        install_payload = json.loads(install.stdout)
        assert Path(".claude/settings.json").exists()
        assert Path(".codex/hooks.json").exists()
        assert Path(".codex/config.toml").exists()
        assert install_payload["item"]["executable_path"]

        status = runner.invoke(app, ["hooks", "status", "-o", "json"])

        assert status.exit_code == 0
        status_payload = json.loads(status.stdout)
        assert status_payload["item"]["claude"]["settings_exists"] is True
        assert status_payload["item"]["codex"]["hooks_exists"] is True
        assert status_payload["item"]["codex"]["feature_enabled"] is True


def test_hidden_hook_commands_do_not_show_in_hooks_help() -> None:
    result = runner.invoke(app, ["hooks", "--help"])

    assert result.exit_code == 0
    assert "install" in result.stdout
    assert "status" in result.stdout
    assert "session-start" not in result.stdout
    assert "session-end" not in result.stdout


def test_hooks_session_start_outputs_toon_home_view_even_with_global_json(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        workspace_dir = Path(".xqueue")
        write_marker(workspace_dir, build_marker("test"))
        _seed_home_database(workspace_dir / "xqueue.db")

        result = runner.invoke(app, ["-o", "json", "hooks", "session-start"])

        assert result.exit_code == 0
        assert "description:" in result.stdout
        assert "queues[1" in result.stdout
        assert "jobs[6" in result.stdout


def test_hooks_session_end_writes_history_and_returns_log_path(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["hooks", "session-end"])

        assert result.exit_code == 0
        payload = decode(result.stdout)
        log_path = Path(payload["item"]["log_path"])
        assert log_path == Path.cwd() / ".xqueue" / "session-history.jsonl"
        assert log_path.exists()

        records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        assert records[-1]["event"] == "session_end"
        assert records[-1]["project_root"] == str(Path.cwd())
