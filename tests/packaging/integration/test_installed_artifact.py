from __future__ import annotations

import shutil
import subprocess
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

#: xcfg 0.5.0 is tagged but unpublished, so an isolated environment cannot
#: resolve it from an index. Until it is published, these tests install it from
#: the same local checkout `[tool.uv.sources]` points at. Both this constant and
#: that source override go away together the moment xcfg reaches an index.
XCFG_SOURCE = REPO_ROOT.parents[1] / "_libs" / "xcfg"


def xcfg_requirement() -> str:
    if not (XCFG_SOURCE / "pyproject.toml").is_file():
        pytest.skip(f"xcfg is not published and no local checkout at {XCFG_SOURCE}")
    return str(XCFG_SOURCE)


@pytest.fixture
def clean_build_tree() -> Iterator[None]:
    """Build from an empty setuptools tree.

    setuptools reuses ``build/lib`` across builds, so a module deleted from
    ``libs/`` can survive there and be packaged into a wheel. That has happened
    twice in this repository; removing the tree prevents it instead of
    detecting it afterwards.
    """
    build_tree = REPO_ROOT / "build"
    shutil.rmtree(build_tree, ignore_errors=True)
    yield
    shutil.rmtree(build_tree, ignore_errors=True)


def build_wheel(artifact_dir: Path) -> Path:
    artifact_dir.mkdir(exist_ok=True)
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(artifact_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return next(artifact_dir.glob("xqueue-*.whl"))


def run_installed(wheel: Path, *command: str, extras: str = "", cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run `command` in a throwaway environment holding only the wheel.

    `extras` selects optional dependencies; the PEP 508 direct-reference form is
    the one uv accepts for a local wheel with extras.
    """
    requirement = f"xqueue{extras} @ file://{wheel}" if extras else str(wheel)
    return subprocess.run(
        ["uv", "run", "--isolated", "--with", xcfg_requirement(), "--with", requirement, *command],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_wheel_contains_runtime_packages_and_installed_cli_runs(tmp_path: Path, clean_build_tree: None) -> None:
    wheel = build_wheel(tmp_path / "artifacts")

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())

    expected_entries = {
        "xqueue/__init__.py",
        "xqueue/py.typed",
        "xqueue/adapters/sqlite/models.py",
        "xqueue/jobs/api.py",
        "xqueue_cli/entry.py",
        "xqueue_cli/main.py",
        "xqueue_cli/renderers/toon.py",
        "xqueue_resources/alembic/env.py",
        "xqueue_resources/logging/default.yaml",
    }
    assert expected_entries <= names
    assert not any(name.startswith("xqueue_libs/") for name in names)
    assert not any(
        name.startswith(f"xqueue/{legacy_package}/")
        for legacy_package in ("actions", "domain", "infra", "services")
        for name in names
    )

    smoke_dir = tmp_path / "installed-smoke"
    smoke_dir.mkdir()
    import_result = run_installed(
        wheel,
        "python",
        "-c",
        "from xqueue import Xqueue; import xqueue; assert xqueue.__all__ == ('ConfigInputs', 'Xqueue'); assert callable(Xqueue.open)",
        cwd=smoke_dir,
    )
    assert import_result.returncode == 0, import_result.stderr

    result = run_installed(wheel, "xq", "--help", extras="[cli]", cwd=smoke_dir)

    assert result.returncode == 0, result.stderr
    assert "durable work queue" in result.stdout.lower()


def test_a_bare_install_omits_the_cli_frameworks(tmp_path: Path, clean_build_tree: None) -> None:
    """An embedder pays for the SDK and nothing else.

    Typer, Rich, and python-toon are imported only under `apps/cli/`, so a
    program that opens `Xqueue` should not have them installed at all.
    """
    wheel = build_wheel(tmp_path / "artifacts")
    smoke_dir = tmp_path / "bare"
    smoke_dir.mkdir()

    sdk = run_installed(wheel, "python", "-c", "from xqueue import Xqueue", cwd=smoke_dir)
    assert sdk.returncode == 0, sdk.stderr

    for framework in ("typer", "rich", "toon"):
        present = run_installed(wheel, "python", "-c", f"import {framework}", cwd=smoke_dir)
        assert present.returncode != 0, f"{framework} is installed by the base distribution"
        assert "ModuleNotFoundError" in present.stderr


def test_xq_without_the_cli_extra_exits_with_a_hint(tmp_path: Path, clean_build_tree: None) -> None:
    """The script stays declared, so it must fail as a tool, not as a traceback."""
    wheel = build_wheel(tmp_path / "artifacts")
    smoke_dir = tmp_path / "bare-script"
    smoke_dir.mkdir()

    result = run_installed(wheel, "xq", "--help", cwd=smoke_dir)

    assert result.returncode == 2, result.stderr
    assert 'pip install "xqueue[cli]"' in result.stderr
    assert "Traceback" not in result.stderr
