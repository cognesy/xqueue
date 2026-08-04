"""The file that makes a directory an xqueue workspace.

A directory named `.xqueue` is not a workspace; a directory holding a valid
`.xqueue/marker.toml` is. The distinction matters when discovery walks up the
tree: without a marker there is nothing to distinguish xqueue's directory from
a coincidence, and operating on the wrong state root is silent data loss.

The marker states product identity and workspace schema, and nothing else. The
database migration head belongs to Alembic, which already owns it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from xqueue.core.errors import InvalidWorkspaceError

#: Directory holding workspace-scoped state, relative to the workspace root.
WORKSPACE_DIR = ".xqueue"

#: Marker filename inside that directory.
MARKER_NAME = "marker.toml"

#: Value of `kind` this product writes and accepts.
WORKSPACE_KIND = "xqueue-workspace"

#: Workspace layout version. Bump when the directory contract changes in a way
#: an older build cannot read; the database schema is Alembic's business.
CURRENT_SCHEMA = 1


class WorkspaceMarker(BaseModel):
    """The parsed contents of `.xqueue/marker.toml`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = Field(min_length=1)
    schema_version: int = Field(ge=1, alias="schema")
    created_by: str = Field(min_length=1)


def marker_path(directory: Path) -> Path:
    """The marker inside a workspace directory (`<root>/.xqueue/`)."""
    return directory / MARKER_NAME


def read_marker(directory: Path) -> WorkspaceMarker | None:
    """Parse the marker in `directory`, or None when there is none.

    Returning None for "absent" and raising for "present but wrong" is the whole
    point: the caller may fall back when a workspace is absent, and must not
    when one is broken.
    """
    path = marker_path(directory)
    if not path.is_file():
        return None

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise InvalidWorkspaceError(
            f"cannot read workspace marker: {path}",
            details={"path": str(path)},
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise InvalidWorkspaceError(
            f"workspace marker is not valid TOML: {path}",
            details={"path": str(path), "reason": str(exc)},
        ) from exc

    try:
        marker = WorkspaceMarker.model_validate(raw)
    except ValueError as exc:
        raise InvalidWorkspaceError(
            f"workspace marker is missing required fields: {path}",
            details={"path": str(path), "reason": str(exc)},
        ) from exc

    if marker.kind != WORKSPACE_KIND:
        raise InvalidWorkspaceError(
            f"{path} belongs to '{marker.kind}', not xqueue",
            details={"path": str(path), "kind": marker.kind},
        )
    if marker.schema_version > CURRENT_SCHEMA:
        raise InvalidWorkspaceError(
            f"workspace schema {marker.schema_version} is newer than this build "
            f"supports ({CURRENT_SCHEMA}); upgrade xqueue",
            details={
                "path": str(path),
                "found": marker.schema_version,
                "supported": CURRENT_SCHEMA,
            },
        )
    return marker


def build_marker(created_by: str) -> WorkspaceMarker:
    return WorkspaceMarker.model_validate({"kind": WORKSPACE_KIND, "schema": CURRENT_SCHEMA, "created_by": created_by})


def render_marker(marker: WorkspaceMarker) -> str:
    """TOML for a marker. Three scalars, so no writer dependency is warranted."""
    return f'kind = "{marker.kind}"\nschema = {marker.schema_version}\ncreated_by = "{marker.created_by}"\n'


def write_marker(directory: Path, marker: WorkspaceMarker) -> Path:
    """Write the marker atomically, so a crash cannot leave a partial one."""
    directory.mkdir(parents=True, exist_ok=True)
    path = marker_path(directory)
    temporary = path.with_suffix(".toml.tmp")
    temporary.write_text(render_marker(marker), encoding="utf-8")
    temporary.replace(path)
    return path
