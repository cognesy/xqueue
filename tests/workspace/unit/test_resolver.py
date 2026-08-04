"""The four resolution steps, in precedence order and one at a time."""

from __future__ import annotations

from pathlib import Path

import pytest
from xqueue.core.errors import InvalidWorkspaceError
from xqueue.workspace.marker import WORKSPACE_DIR, build_marker, marker_path, write_marker
from xqueue.workspace.paths import WorkspaceScope
from xqueue.workspace.resolver import (
    HOME_ENV_VAR,
    ROOT_ENV_VAR,
    discover_workspace,
    home_workspace,
    project_workspace,
    resolve_workspace,
)


def make_workspace(root: Path) -> Path:
    """A real, discoverable workspace at `root`."""
    root.mkdir(parents=True, exist_ok=True)
    write_marker(root / WORKSPACE_DIR, build_marker("test"))
    return root


# --- precedence ------------------------------------------------------------
#
# Each test sets up *every* lower-priority signal as well, so a passing test
# means the step won rather than that it was the only candidate.


def test_step_1_an_explicit_root_beats_everything_below(tmp_path: Path) -> None:
    explicit = make_workspace(tmp_path / "explicit")
    configured = make_workspace(tmp_path / "configured")
    nearby = make_workspace(tmp_path / "nearby")

    resolved = resolve_workspace(
        explicit_root=explicit,
        start_dir=nearby,
        environ={ROOT_ENV_VAR: str(configured), HOME_ENV_VAR: str(tmp_path / "home")},
    )

    assert resolved.root == explicit.resolve()
    assert resolved.scope is WorkspaceScope.PROJECT


def test_step_2_xqueue_root_beats_discovery_and_home(tmp_path: Path) -> None:
    configured = make_workspace(tmp_path / "configured")
    nearby = make_workspace(tmp_path / "nearby")

    resolved = resolve_workspace(
        start_dir=nearby,
        environ={ROOT_ENV_VAR: str(configured), HOME_ENV_VAR: str(tmp_path / "home")},
    )

    assert resolved.root == configured.resolve()


def test_step_3_discovery_beats_home(tmp_path: Path) -> None:
    nearby = make_workspace(tmp_path / "nearby")

    resolved = resolve_workspace(
        start_dir=nearby,
        environ={HOME_ENV_VAR: str(tmp_path / "home")},
    )

    assert resolved.root == nearby.resolve()
    assert resolved.scope is WorkspaceScope.PROJECT


def test_step_4_home_is_the_answer_when_nothing_else_applies(tmp_path: Path) -> None:
    """No workspace here is a normal answer -- there is no NotFound error."""
    plain = tmp_path / "plain"
    plain.mkdir()

    resolved = resolve_workspace(
        start_dir=plain,
        environ={HOME_ENV_VAR: str(tmp_path / "home")},
    )

    assert resolved.scope is WorkspaceScope.HOME
    assert resolved.directory == tmp_path / "home"


def test_discovery_is_skipped_entirely_without_a_start_directory(tmp_path: Path) -> None:
    """The SDK does not have to have a working directory; the CLI supplies one."""
    make_workspace(tmp_path / "nearby")

    resolved = resolve_workspace(environ={HOME_ENV_VAR: str(tmp_path / "home")})

    assert resolved.scope is WorkspaceScope.HOME


def test_an_empty_xqueue_root_does_not_count_as_set(tmp_path: Path) -> None:
    nearby = make_workspace(tmp_path / "nearby")

    resolved = resolve_workspace(
        start_dir=nearby,
        environ={ROOT_ENV_VAR: "", HOME_ENV_VAR: str(tmp_path / "home")},
    )

    assert resolved.root == nearby.resolve()


# --- discovery -------------------------------------------------------------


def test_discovery_walks_up_from_a_nested_directory(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    nested = root / "src" / "deep" / "deeper"
    nested.mkdir(parents=True)

    discovered = discover_workspace(nested)

    assert discovered is not None
    assert discovered.root == root.resolve()
    assert discovered.directory == (root / WORKSPACE_DIR).resolve()


def test_discovery_stops_at_the_nearest_workspace(tmp_path: Path) -> None:
    outer = make_workspace(tmp_path / "outer")
    inner = make_workspace(outer / "inner")

    discovered = discover_workspace(inner / "src")

    assert discovered is not None
    assert discovered.root == inner.resolve()


def test_discovery_returns_none_when_there_is_nothing_to_find(tmp_path: Path) -> None:
    plain = tmp_path / "plain" / "deeper"
    plain.mkdir(parents=True)

    assert discover_workspace(plain) is None


def test_a_bare_directory_named_xqueue_is_not_a_workspace(tmp_path: Path) -> None:
    """Without a marker there is nothing to tell it apart from a coincidence."""
    (tmp_path / "project" / WORKSPACE_DIR).mkdir(parents=True)

    assert discover_workspace(tmp_path / "project") is None


def test_a_malformed_marker_raises_rather_than_being_walked_past(tmp_path: Path) -> None:
    """Operating on the wrong state root is silent data loss, so this stops."""
    outer = make_workspace(tmp_path / "outer")
    broken = outer / "broken"
    (broken / WORKSPACE_DIR).mkdir(parents=True)
    marker_path(broken / WORKSPACE_DIR).write_text("kind = = =\n", encoding="utf-8")

    with pytest.raises(InvalidWorkspaceError):
        discover_workspace(broken)


# --- the two named-root helpers -------------------------------------------


def test_a_named_root_without_a_marker_is_uninitialized_not_invalid(tmp_path: Path) -> None:
    """Steps 1 and 2 name a directory outright; init fills it in later."""
    workspace = project_workspace(tmp_path / "fresh")

    assert workspace.scope is WorkspaceScope.PROJECT
    assert workspace.is_initialized is False
    assert workspace.directory == (tmp_path / "fresh" / WORKSPACE_DIR).resolve()


def test_a_named_root_with_a_broken_marker_still_raises(tmp_path: Path) -> None:
    directory = tmp_path / "named" / WORKSPACE_DIR
    directory.mkdir(parents=True)
    marker_path(directory).write_text('kind = "other"\nschema = 1\ncreated_by = "x"\n', encoding="utf-8")

    with pytest.raises(InvalidWorkspaceError):
        project_workspace(tmp_path / "named")


def test_the_home_workspace_honours_xqueue_home(tmp_path: Path) -> None:
    workspace = home_workspace(environ={HOME_ENV_VAR: str(tmp_path / "elsewhere")})

    assert workspace.scope is WorkspaceScope.HOME
    assert workspace.directory == tmp_path / "elsewhere"


def test_the_home_workspace_falls_back_to_the_users_home(tmp_path: Path) -> None:
    workspace = home_workspace(environ={})

    assert workspace.directory == Path.home() / WORKSPACE_DIR
