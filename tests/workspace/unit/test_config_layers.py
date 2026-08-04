"""`config show` has to be able to say where a value came from."""

from __future__ import annotations

from pathlib import Path

import pytest
from xqueue.workspace.inputs import ConfigInputs
from xqueue.workspace.loader import CONFIG_NAME, SettingsLoader
from xqueue.workspace.models import EffectiveConfig
from xqueue.workspace.paths import Workspace
from xqueue.workspace.resolver import project_workspace


@pytest.fixture
def packaged(tmp_path: Path) -> Path:
    root = tmp_path / "packaged"
    root.mkdir()
    (root / "config.default.yaml").write_text("worker:\n  retry_delay_seconds: 1\n")
    return root


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    return project_workspace(tmp_path / "project")


def load(packaged: Path, workspace: Workspace, **kwargs) -> EffectiveConfig:
    return SettingsLoader(config_root=packaged).load(
        workspace,
        inputs=kwargs.pop("inputs", ConfigInputs()),
        environ=kwargs.pop("environ", {}),
    )


def applied(config: EffectiveConfig) -> list[str]:
    return [layer.layer for layer in config.layers if layer.applied]


def names(config: EffectiveConfig) -> list[str]:
    return [layer.layer for layer in config.layers]


def test_the_chain_is_reported_base_first(packaged: Path, workspace: Workspace) -> None:
    config = load(packaged, workspace)

    assert names(config) == ["packaged-default", "user", "workspace", "environment", "override"]


def test_absent_layers_are_listed_but_not_applied(packaged: Path, workspace: Workspace) -> None:
    """Naming a layer that contributed nothing is how an operator learns it exists."""
    config = load(packaged, workspace)

    assert applied(config) == ["packaged-default"]
    assert all(layer.origin for layer in config.layers)


def test_a_workspace_file_shows_as_applied(packaged: Path, workspace: Workspace) -> None:
    workspace.directory.mkdir(parents=True)
    (workspace.directory / CONFIG_NAME).write_text("worker:\n  retry_delay_seconds: 3\n")

    config = load(packaged, workspace)

    assert applied(config) == ["packaged-default", "workspace"]
    assert next(x for x in config.layers if x.layer == "workspace").origin == str(workspace.directory / CONFIG_NAME)


def test_an_explicit_file_displaces_the_packaged_default(packaged: Path, workspace: Workspace, tmp_path: Path) -> None:
    explicit = tmp_path / "explicit.yaml"
    explicit.write_text("worker:\n  retry_delay_seconds: 9\n")

    config = load(packaged, workspace, inputs=ConfigInputs(config_path=explicit))

    assert "explicit-file" in applied(config)
    assert "packaged-default" not in applied(config)


def test_a_named_env_appears_between_the_default_and_the_user_layer(packaged: Path, workspace: Workspace) -> None:
    (packaged / "config.staging.yaml").write_text("worker:\n  retry_delay_seconds: 5\n")

    config = load(packaged, workspace, inputs=ConfigInputs(env_name="staging"))

    assert names(config)[:3] == ["packaged-default", "env-overlay", "user"]
    assert applied(config)[:2] == ["packaged-default", "env-overlay"]


def test_the_environment_layer_names_the_variables_it_used(packaged: Path, workspace: Workspace) -> None:
    config = load(
        packaged,
        workspace,
        environ={"XQUEUE_WORKER__RETRY_DELAY_SECONDS": "8", "XQUEUE_HOME": "/somewhere"},
    )

    layer = next(x for x in config.layers if x.layer == "environment")

    assert layer.applied
    # The flat variable is not a settings override and must not be listed.
    assert layer.origin == "XQUEUE_WORKER__RETRY_DELAY_SECONDS"


def test_the_override_layer_names_the_paths_it_set(packaged: Path, workspace: Workspace) -> None:
    config = load(
        packaged,
        workspace,
        inputs=ConfigInputs(overrides={"worker.retry_delay_seconds": "7"}),
    )

    layer = next(x for x in config.layers if x.layer == "override")

    assert layer.applied
    assert layer.origin == "worker.retry_delay_seconds"
