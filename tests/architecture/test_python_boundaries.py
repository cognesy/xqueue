from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "python_boundaries"
CHECKER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_python_boundaries.py"
SPEC = importlib.util.spec_from_file_location("xqueue_boundary_checker", CHECKER_PATH)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)
check_source = CHECKER.check_source
scan_repository = CHECKER.scan_repository


@pytest.mark.parametrize(
    ("fixture", "rule"),
    [
        ("violations/adapter_cli_import.txt", "adapters-no-channel-imports"),
        ("violations/cli_adapter_import.txt", "cli-sealed-boundary"),
        ("violations/cli_sqlalchemy_import.txt", "cli-sealed-boundary"),
        ("violations/cli_worker_internal_import.txt", "cli-sdk-only"),
        # A CLI file nobody enumerated is still a CLI file.
        ("violations/cli_unlisted_file_internal_import.txt", "cli-sdk-only"),
        # A capability module nobody enumerated is still private.
        ("violations/cli_new_capability_internal_import.txt", "cli-sdk-only"),
        ("violations/core_capability_import.txt", "core-no-upward-imports"),
        ("violations/queues_private_jobs_import.txt", "queues-public-jobs-contract-only"),
        # A capability answering "which workspace am I in" for itself.
        ("violations/capability_resolver_import.txt", "capabilities-do-not-resolve-workspaces"),
    ],
)
def test_violation_fixtures_are_rejected(fixture: str, rule: str) -> None:
    path = FIXTURES / fixture
    logical_path, source = path.read_text().split("\n---\n", 1)

    violations = check_source(logical_path, source)

    assert {item.rule for item in violations} == {rule}


@pytest.mark.parametrize(
    "fixture",
    [
        "legal/adapter_core_import.txt",
        "legal/cli_sdk_import.txt",
        "legal/cli_capability_models_import.txt",
        "legal/cli_logging_bootstrap_import.txt",
        "legal/core_stdlib_import.txt",
        "legal/queues_jobs_model_import.txt",
        # Naming the Workspace type is fine; only deciding one is not.
        "legal/capability_workspace_type_import.txt",
    ],
)
def test_legal_fixtures_are_accepted(fixture: str) -> None:
    path = FIXTURES / fixture
    logical_path, source = path.read_text().split("\n---\n", 1)

    assert check_source(logical_path, source) == []


def test_repository_obeys_python_boundaries() -> None:
    assert scan_repository() == []
