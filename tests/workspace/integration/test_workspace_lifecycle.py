"""The workspace as an operator and an embedder actually meet it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner
from xqueue import Xqueue
from xqueue.adapters.sqlite.database import create_sqlite_engine
from xqueue.adapters.sqlite.models import Base
from xqueue.core.errors import InvalidWorkspaceError
from xqueue.workspace.marker import WORKSPACE_DIR, build_marker, marker_path, read_marker, write_marker
from xqueue.workspace.paths import WorkspaceScope
from xqueue.workspace.resolver import project_workspace, resolve_workspace
from xqueue_cli.main import app

runner = CliRunner()


def test_workspace_init_creates_a_discoverable_workspace(tmp_path: Path) -> None:
    result = runner.invoke(app, ["workspace", "init", "--root", str(tmp_path), "--output", "json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["item"]["scope"] == "project"

    # The proof that init worked is that discovery now finds it.
    discovered = resolve_workspace(start_dir=tmp_path)
    assert discovered.root == tmp_path.resolve()
    assert discovered.is_initialized


def test_workspace_init_is_idempotent_through_the_cli(tmp_path: Path) -> None:
    runner.invoke(app, ["workspace", "init", "--root", str(tmp_path), "--output", "json"])
    result = runner.invoke(app, ["workspace", "init", "--root", str(tmp_path), "--output", "json"])

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["item"]["created_paths"] == []


def test_workspace_init_defaults_to_the_current_directory(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["workspace", "init", "--output", "json"])

        assert result.exit_code == 0, result.stdout
        assert read_marker(Path(WORKSPACE_DIR)) is not None


def test_a_client_opens_the_workspace_discovery_finds(tmp_path: Path) -> None:
    write_marker(tmp_path / WORKSPACE_DIR, build_marker("test"))
    nested = tmp_path / "src" / "deep"
    nested.mkdir(parents=True)

    with Xqueue.open(workspace_root=nested) as client:
        paths = client.workspace.config().paths

    assert paths.state_root == tmp_path.resolve() / WORKSPACE_DIR
    assert paths.database_path == tmp_path.resolve() / WORKSPACE_DIR / "xqueue.db"


def test_a_directory_with_no_workspace_falls_back_to_the_home_instance(
    tmp_path: Path,
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    xqueue_home = Path(__import__("os").environ["XQUEUE_HOME"])

    with Xqueue.open(workspace_root=plain) as client:
        paths = client.workspace.config().paths

    assert paths.state_root == xqueue_home


def test_a_broken_marker_refuses_to_open_rather_than_falling_back(tmp_path: Path) -> None:
    directory = tmp_path / WORKSPACE_DIR
    directory.mkdir()
    marker_path(directory).write_text('kind = "other-tool"\nschema = 1\ncreated_by = "x"\n', encoding="utf-8")

    with pytest.raises(InvalidWorkspaceError):
        Xqueue.open(workspace_root=tmp_path)


def test_two_clients_on_two_workspaces_coexist_in_one_process(tmp_path: Path) -> None:
    """Nothing about a workspace is process-global, and this is the proof."""
    left = tmp_path / "left"
    right = tmp_path / "right"

    with (
        Xqueue.open(workspace=project_workspace(left)) as left_client,
        Xqueue.open(workspace=project_workspace(right)) as right_client,
    ):
        left_client.workspace.init()
        right_client.workspace.init()

        left_paths = left_client.workspace.config().paths
        right_paths = right_client.workspace.config().paths
        for paths in (left_paths, right_paths):
            engine = create_sqlite_engine(paths.database_path)
            Base.metadata.create_all(engine)
            engine.dispose()

        left_job = left_client.jobs.enqueue(command="echo left", queue="default")

        assert left_paths.database_path == left.resolve() / WORKSPACE_DIR / "xqueue.db"
        assert right_paths.database_path == right.resolve() / WORKSPACE_DIR / "xqueue.db"

        # Same process, same schema, entirely separate state.
        assert left_client.jobs.show(left_job.id).command == "echo left"
        assert right_client.jobs.list() == []


def test_a_passed_workspace_skips_resolution_entirely(tmp_path: Path) -> None:
    """An explicit workspace wins even against a workspace under the cwd."""
    write_marker(tmp_path / "discoverable" / WORKSPACE_DIR, build_marker("test"))
    chosen = project_workspace(tmp_path / "chosen")

    with Xqueue.open(workspace=chosen, workspace_root=tmp_path / "discoverable") as client:
        assert client.workspace.config().paths.state_root == chosen.directory


def test_the_home_scope_keeps_repo_local_artifacts_in_the_callers_directory(
    tmp_path: Path,
) -> None:
    """Hooks belong to the directory the operator named, not to `~`."""
    plain = tmp_path / "plain"
    plain.mkdir()

    with Xqueue.open(workspace_root=plain) as client:
        status = client.workspace.hook_status()

    assert status.claude.settings_path.startswith(str(plain.resolve()))


def test_the_workspace_scope_is_reported_for_both_kinds(tmp_path: Path) -> None:
    write_marker(tmp_path / WORKSPACE_DIR, build_marker("test"))

    project = resolve_workspace(start_dir=tmp_path)
    home = resolve_workspace(start_dir=tmp_path / "..")

    assert project.scope is WorkspaceScope.PROJECT
    assert home.scope is WorkspaceScope.HOME
