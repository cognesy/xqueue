"""`workspace init` is idempotent and never destroys what it did not write."""

from __future__ import annotations

from pathlib import Path

from xqueue.workspace.init import STARTER_CONFIG, WorkspaceInitService
from xqueue.workspace.marker import WORKSPACE_DIR, marker_path, read_marker
from xqueue.workspace.resolver import project_workspace


def initialize(root: Path, *, created_by: str = "xqueue test", force: bool = False):
    return WorkspaceInitService().initialize(project_workspace(root), created_by=created_by, force=force)


def test_init_creates_the_whole_directory(tmp_path: Path) -> None:
    result = initialize(tmp_path)

    directory = tmp_path / WORKSPACE_DIR
    assert directory.is_dir()
    assert (directory / "run").is_dir()
    assert (directory / "logs").is_dir()
    assert (directory / "config.yaml").read_text() == STARTER_CONFIG
    assert read_marker(directory) is not None
    assert result.conflicting_paths == []
    assert str(marker_path(directory)) in result.created_paths


def test_init_records_who_created_the_workspace(tmp_path: Path) -> None:
    initialize(tmp_path, created_by="xqueue 9.9.9")

    marker = read_marker(tmp_path / WORKSPACE_DIR)

    assert marker is not None
    assert marker.created_by == "xqueue 9.9.9"


def test_running_init_twice_changes_nothing(tmp_path: Path) -> None:
    initialize(tmp_path)
    directory = tmp_path / WORKSPACE_DIR
    (directory / "config.yaml").write_text("queue:\n  default_queue: mine\n")
    before = read_marker(directory)

    second = initialize(tmp_path)

    assert second.created_paths == []
    assert set(second.retained_paths) == {
        str(directory),
        str(directory / "run"),
        str(directory / "logs"),
        str(marker_path(directory)),
        str(directory / "config.yaml"),
        str(directory / "xqueue.db"),
    }
    assert (directory / "config.yaml").read_text() == "queue:\n  default_queue: mine\n"
    assert read_marker(directory) == before


def test_init_completes_a_partial_workspace(tmp_path: Path) -> None:
    """A directory someone made by hand is filled in, not rejected."""
    directory = tmp_path / WORKSPACE_DIR
    (directory / "logs").mkdir(parents=True)

    result = initialize(tmp_path)

    assert (directory / "run").is_dir()
    assert str(directory / "logs") in result.retained_paths
    assert str(directory / "run") in result.created_paths


def test_force_rewrites_config_and_removes_nothing_else(tmp_path: Path) -> None:
    initialize(tmp_path)
    directory = tmp_path / WORKSPACE_DIR
    (directory / "config.yaml").write_text("queue:\n  default_queue: mine\n")
    (directory / "xqueue.db").write_text("sqlite-data")
    (directory / "logs" / "worker.log").write_text("hello\n")

    result = initialize(tmp_path, force=True)

    assert (directory / "config.yaml").read_text() == STARTER_CONFIG
    assert str(directory / "config.yaml") in result.created_paths
    # Everything the operator owns survives a --force.
    assert (directory / "xqueue.db").read_text() == "sqlite-data"
    assert (directory / "logs" / "worker.log").read_text() == "hello\n"
    assert read_marker(directory) is not None


def test_a_file_where_the_directory_belongs_is_reported_not_removed(tmp_path: Path) -> None:
    """Deleting the operator's file is their decision, not init's."""
    occupied = tmp_path / WORKSPACE_DIR
    occupied.write_text("not a directory")

    result = initialize(tmp_path)

    assert result.conflicting_paths == [str(occupied)]
    assert result.created_paths == []
    assert occupied.read_text() == "not a directory"


def test_a_file_where_a_subdirectory_belongs_is_reported(tmp_path: Path) -> None:
    directory = tmp_path / WORKSPACE_DIR
    directory.mkdir()
    (directory / "run").write_text("not a directory")

    result = initialize(tmp_path)

    assert str(directory / "run") in result.conflicting_paths
    assert (directory / "logs").is_dir()


def test_init_leaves_no_temporary_files_behind(tmp_path: Path) -> None:
    initialize(tmp_path)

    directory = tmp_path / WORKSPACE_DIR

    assert not any(p.name.endswith(".tmp") for p in directory.iterdir())


def test_init_leaves_a_database_an_operator_can_enqueue_into(tmp_path: Path) -> None:
    """The gap this closes: `init` reported success, then `enqueue` failed with
    "no such table: jobs" because nothing on the init path ran migrations."""
    from sqlalchemy import create_engine, inspect

    result = initialize(tmp_path)

    database_path = tmp_path / WORKSPACE_DIR / "xqueue.db"
    assert database_path.exists()
    assert str(database_path) in result.created_paths

    tables = set(inspect(create_engine(f"sqlite:///{database_path}")).get_table_names())
    assert {"jobs", "queues", "workers", "attempts", "events"} <= tables


def test_init_twice_keeps_the_database_it_already_made(tmp_path: Path) -> None:
    """Migrating to head is idempotent, so the second run retains rather than recreates."""
    initialize(tmp_path)
    database_path = tmp_path / WORKSPACE_DIR / "xqueue.db"
    stamped = database_path.read_bytes()

    result = initialize(tmp_path)

    assert str(database_path) in result.retained_paths
    assert str(database_path) not in result.created_paths
    assert database_path.read_bytes() == stamped


def test_a_file_that_is_not_a_database_is_reported_not_migrated(tmp_path: Path) -> None:
    """Same rule as the directory case: report it, never delete the operator's file."""
    initialize(tmp_path)
    database_path = tmp_path / WORKSPACE_DIR / "xqueue.db"
    database_path.write_text("definitely not sqlite")

    result = initialize(tmp_path)

    assert str(database_path) in result.conflicting_paths
    assert database_path.read_text() == "definitely not sqlite"
