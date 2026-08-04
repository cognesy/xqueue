from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "import_linter"
REPO_ROOT = Path(__file__).resolve().parents[2]

#: (contract name, fixture directory, contracts the fixture declares). The count
#: is asserted so a fixture that silently stops declaring a contract cannot pass
#: by declaring fewer.
CONTRACT_FIXTURES = [
    ("Capabilities depend downward only", "violation_capability_dag", 3),
    ("Workspace and configuration do not depend on runtime capabilities", "violation_workspace", 3),
    ("Capabilities do not import the runtime composition root", "violation_composition", 3),
    ("Only the workspace loader imports the configuration library", "violation_xcfg", 4),
]


def _lint_imports(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["lint-imports", "--no-cache"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_repository_import_contracts_pass() -> None:
    result = _lint_imports(REPO_ROOT)

    assert result.returncode == 0, result.stdout + result.stderr


def test_repository_enforces_the_capability_dag() -> None:
    """The capability graph must be a contract, not a convention."""
    result = _lint_imports(REPO_ROOT)

    for contract, _, _ in CONTRACT_FIXTURES:
        assert f"{contract} KEPT" in result.stdout, result.stdout


def test_legal_import_fixture_passes() -> None:
    result = _lint_imports(FIXTURES / "legal")

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(("contract", "fixture", "declared"), CONTRACT_FIXTURES)
def test_each_capability_contract_can_fail(contract: str, fixture: str, declared: int) -> None:
    """A contract nothing can break is a contract that proves nothing."""
    result = _lint_imports(FIXTURES / fixture)

    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{contract} BROKEN" in result.stdout
    assert f"Contracts: {declared - 1} kept, 1 broken." in result.stdout
