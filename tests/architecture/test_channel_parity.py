"""The declared architecture documents must agree with the code.

`docs/dev/channel-parity.md` and `docs/dev/plane-map.md` are the two artifacts
the house template requires. A document nobody checks decays in one sprint, so
these tests read both and compare them against the real SDK facets and the real
command contracts. Adding a facet method or a contract fails here until the
documents record it.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest
from xqueue_cli.axi_contracts import COMMAND_CONTRACTS

DOCS = Path(__file__).resolve().parents[2] / "docs" / "dev"
PARITY = DOCS / "channel-parity.md"
PLANE_MAP = DOCS / "plane-map.md"

#: Facet name -> the class exposed by `xqueue.<facet>.api`.
FACETS = {
    "jobs": "Jobs",
    "queues": "Queues",
    "workers": "Workers",
    "controller": "Controller",
    "maintenance": "Maintenance",
    "workspace": "Workspace",
}

PLANES = ("Data", "Control", "Management")

#: Cell content standing for "no operation", in either table.
NONE_CELL = "—"

_ROW = re.compile(r"^\|(?P<first>[^|]+)\|(?P<second>[^|]+)\|\s*$")
_CODE = re.compile(r"`([^`]+)`")


def facet_methods() -> set[str]:
    """Every public method on every SDK facet, as `facet.method`."""
    found: set[str] = set()
    for facet, class_name in FACETS.items():
        api = importlib.import_module(f"xqueue.{facet}.api")
        facade = getattr(api, class_name)
        found |= {
            f"{facet}.{name}" for name, value in vars(facade).items() if not name.startswith("_") and callable(value)
        }
    return found


def _table_rows(document: Path, heading: str) -> list[tuple[str, str]]:
    """Two-column rows under `heading`, skipping the header and delimiter."""
    lines = document.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    rows: list[tuple[str, str]] = []
    for line in lines[start:]:
        if line.startswith("#") and line.strip() != heading:
            if rows:
                break
            continue
        match = _ROW.match(line)
        if match is None:
            continue
        first = match["first"].strip()
        second = match["second"].strip()
        if first in {"Contract", "Operation"} or set(first) <= {"-", " "}:
            continue
        rows.append((first, second))
    return rows


def contract_rows() -> dict[str, tuple[str, ...]]:
    """Contract name -> the operations it is documented to call."""
    rows = _table_rows(PARITY, "## CLI Contracts")
    mapping: dict[str, tuple[str, ...]] = {}
    for contract_cell, operation_cell in rows:
        contract = _one_code_span(contract_cell)
        operations = tuple(_CODE.findall(operation_cell))
        assert contract not in mapping, f"{contract} listed twice in channel-parity.md"
        mapping[contract] = operations
    return mapping


def sdk_only_rows() -> dict[str, str]:
    """Operation -> the stated reason the CLI does not expose it."""
    rows = _table_rows(PARITY, "## Operations the CLI Does Not Expose")
    return {_one_code_span(operation): reason for operation, reason in rows}


def plane_assignments() -> dict[str, str]:
    """Operation -> plane, read from the fenced blocks in the plane map."""
    lines = PLANE_MAP.read_text(encoding="utf-8").splitlines()
    assignments: dict[str, str] = {}
    plane: str | None = None
    inside = False
    for line in lines:
        first_word = line.split(" ", 1)[0].rstrip(":")
        if not inside and first_word in PLANES and line.rstrip().endswith(":"):
            plane = first_word.lower()
            continue
        if line.startswith("```"):
            inside = not inside and plane is not None
            if not inside:
                plane = None
            continue
        if inside and plane is not None:
            for name in line.split():
                assert name not in assignments, f"{name} appears in two planes"
                assignments[name] = plane
    return assignments


def _one_code_span(cell: str) -> str:
    if cell == NONE_CELL:
        return NONE_CELL
    spans = _CODE.findall(cell)
    assert len(spans) == 1, f"expected one code span in {cell!r}, found {spans}"
    return spans[0]


# -- channel parity ------------------------------------------------------


def test_every_command_contract_has_exactly_one_row() -> None:
    documented = set(contract_rows())
    declared = set(COMMAND_CONTRACTS)
    assert documented == declared, (
        "docs/dev/channel-parity.md disagrees with COMMAND_CONTRACTS; "
        f"undocumented: {sorted(declared - documented)}; "
        f"stale rows: {sorted(documented - declared)}"
    )


def test_every_documented_operation_is_a_real_facet_method() -> None:
    methods = facet_methods()
    named = {operation for operations in contract_rows().values() for operation in operations if operation != NONE_CELL}
    assert named <= methods, f"channel-parity.md names methods that do not exist: {sorted(named - methods)}"


def test_every_facet_method_is_documented_somewhere() -> None:
    exposed = {operation for operations in contract_rows().values() for operation in operations}
    documented = exposed | set(sdk_only_rows())
    missing = facet_methods() - documented
    assert not missing, (
        "docs/dev/channel-parity.md has no row for "
        f"{sorted(missing)}: add a contract row, or a row stating why the CLI "
        "does not expose it"
    )


def test_sdk_only_operations_are_real_and_absent_from_the_cli() -> None:
    sdk_only = sdk_only_rows()
    methods = facet_methods()
    assert set(sdk_only) <= methods, f"not facet methods: {sorted(set(sdk_only) - methods)}"
    exposed = {operation for operations in contract_rows().values() for operation in operations}
    both = set(sdk_only) & exposed
    assert not both, f"{sorted(both)} is listed as CLI-absent but a contract calls it"
    for operation, reason in sdk_only.items():
        assert reason and reason != NONE_CELL, f"{operation} needs a stated reason"


# -- plane map -----------------------------------------------------------


def test_the_plane_map_covers_every_facet_method_once() -> None:
    assigned = plane_assignments()
    methods = facet_methods()
    assert set(assigned) == methods, (
        "docs/dev/plane-map.md disagrees with the SDK facets; "
        f"unassigned: {sorted(methods - set(assigned))}; "
        f"stale: {sorted(set(assigned) - methods)}"
    )


@pytest.mark.parametrize("plane", [plane.lower() for plane in PLANES])
def test_each_plane_is_populated(plane: str) -> None:
    assert plane in plane_assignments().values()
