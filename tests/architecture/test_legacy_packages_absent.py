from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "xqueue.actions",
        "xqueue.domain",
        "xqueue.infra",
        "xqueue.services",
    ],
)
def test_global_technical_layer_package_is_absent(module: str) -> None:
    assert importlib.util.find_spec(module) is None


@pytest.mark.parametrize("directory", ["actions", "domain", "infra", "services"])
def test_test_tree_does_not_name_a_deleted_layer(directory: str) -> None:
    """Tests are filed under the capability or channel they exercise."""
    repository_root = Path(__file__).resolve().parents[2]
    assert not (repository_root / "tests" / directory).exists()
