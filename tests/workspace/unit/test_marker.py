"""The marker is what makes a directory a workspace, so it is tested first."""

from __future__ import annotations

from pathlib import Path

import pytest
from xqueue.core.errors import InvalidWorkspaceError
from xqueue.workspace.marker import (
    CURRENT_SCHEMA,
    WORKSPACE_KIND,
    build_marker,
    marker_path,
    read_marker,
    write_marker,
)


def test_a_written_marker_reads_back_identical(tmp_path: Path) -> None:
    written = build_marker("xqueue 1.2.3")

    write_marker(tmp_path, written)

    assert read_marker(tmp_path) == written
    assert written.kind == WORKSPACE_KIND
    assert written.schema_version == CURRENT_SCHEMA
    assert written.created_by == "xqueue 1.2.3"


def test_an_absent_marker_is_not_an_error(tmp_path: Path) -> None:
    """Absent means "no workspace here", which callers are allowed to handle."""
    assert read_marker(tmp_path) is None
    assert read_marker(tmp_path / "nowhere") is None


def test_a_newer_schema_is_refused_rather_than_guessed_at(tmp_path: Path) -> None:
    marker_path(tmp_path).write_text(
        f'kind = "{WORKSPACE_KIND}"\nschema = {CURRENT_SCHEMA + 1}\ncreated_by = "xqueue from the future"\n',
        encoding="utf-8",
    )

    with pytest.raises(InvalidWorkspaceError) as caught:
        read_marker(tmp_path)

    assert caught.value.details["found"] == CURRENT_SCHEMA + 1
    assert caught.value.details["supported"] == CURRENT_SCHEMA


def test_an_older_schema_is_accepted(tmp_path: Path) -> None:
    """Only *newer* is unreadable; this build understands what it has shipped."""
    marker_path(tmp_path).write_text(
        f'kind = "{WORKSPACE_KIND}"\nschema = 1\ncreated_by = "xqueue 0.1.0"\n',
        encoding="utf-8",
    )

    marker = read_marker(tmp_path)

    assert marker is not None
    assert marker.schema_version == 1


def test_another_products_marker_is_refused(tmp_path: Path) -> None:
    marker_path(tmp_path).write_text(
        'kind = "some-other-tool"\nschema = 1\ncreated_by = "not us"\n',
        encoding="utf-8",
    )

    with pytest.raises(InvalidWorkspaceError, match="not xqueue"):
        read_marker(tmp_path)


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("kind = = =\n", "not valid TOML"),
        ('kind = "xqueue-workspace"\n', "missing required fields"),
        ('kind = ""\nschema = 1\ncreated_by = "x"\n', "missing required fields"),
        ('kind = "xqueue-workspace"\nschema = 0\ncreated_by = "x"\n', "missing required fields"),
    ],
)
def test_a_malformed_marker_raises(tmp_path: Path, content: str, match: str) -> None:
    marker_path(tmp_path).write_text(content, encoding="utf-8")

    with pytest.raises(InvalidWorkspaceError, match=match):
        read_marker(tmp_path)


def test_writing_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    write_marker(tmp_path, build_marker("xqueue"))

    assert sorted(p.name for p in tmp_path.iterdir()) == ["marker.toml"]
