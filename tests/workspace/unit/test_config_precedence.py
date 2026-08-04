"""The precedence contract, one adjacent pair at a time.

Each test sets the *same* key in two neighbouring layers and asserts which one
survives. Testing adjacent pairs rather than the whole stack is what makes a
failure say where the order broke.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from xqueue.core.errors import ConfigurationError
from xqueue.workspace.inputs import ConfigInputs
from xqueue.workspace.loader import CONFIG_ENV_VAR, CONFIG_NAME, ENV_NAME_VAR, SettingsLoader
from xqueue.workspace.paths import Workspace, WorkspaceScope
from xqueue.workspace.resolver import project_workspace

RETRY = "worker:\n  retry_delay_seconds: {}\n"


@pytest.fixture
def packaged(tmp_path: Path) -> Path:
    """A packaged config root standing in for `xqueue_resources/config`."""
    root = tmp_path / "packaged"
    root.mkdir()
    (root / "config.default.yaml").write_text("queue:\n  default_queue: default\nworker:\n  retry_delay_seconds: 1\n")
    return root


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    return project_workspace(tmp_path / "project")


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def load(
    packaged: Path,
    workspace: Workspace,
    *,
    inputs: ConfigInputs | None = None,
    environ: dict[str, str] | None = None,
):
    return SettingsLoader(config_root=packaged).load(
        workspace,
        inputs=inputs or ConfigInputs(),
        environ=environ or {},
    )


# --- the base chain --------------------------------------------------------


def test_an_explicit_file_replaces_the_packaged_default(packaged: Path, workspace: Workspace, tmp_path: Path) -> None:
    explicit = write(tmp_path / "explicit.yaml", RETRY.format(99))

    config = load(packaged, workspace, inputs=ConfigInputs(config_path=explicit))

    assert config.worker.retry_delay_seconds == 99
    # Replaces, rather than layers over: the default's queue name is gone and
    # the model's own default takes its place.
    assert config.queue.default_queue == "default"


def test_an_explicit_file_beats_a_named_env(packaged: Path, workspace: Workspace, tmp_path: Path) -> None:
    write(packaged / "config.staging.yaml", RETRY.format(50))
    explicit = write(tmp_path / "explicit.yaml", RETRY.format(99))

    config = load(
        packaged,
        workspace,
        inputs=ConfigInputs(config_path=explicit, env_name="staging"),
    )

    assert config.worker.retry_delay_seconds == 99


def test_a_named_env_beats_the_packaged_default(packaged: Path, workspace: Workspace) -> None:
    write(packaged / "config.staging.yaml", RETRY.format(50))

    config = load(packaged, workspace, inputs=ConfigInputs(env_name="staging"))

    assert config.worker.retry_delay_seconds == 50


def test_a_named_env_states_only_what_it_changes(packaged: Path, workspace: Workspace) -> None:
    """It layers over the default, so unmentioned keys survive."""
    write(packaged / "config.staging.yaml", RETRY.format(50))

    config = load(packaged, workspace, inputs=ConfigInputs(env_name="staging"))

    assert config.worker.retry_delay_seconds == 50
    assert config.queue.default_queue == "default"


# --- the merge chain -------------------------------------------------------


def test_the_user_layer_beats_the_base(packaged: Path, workspace: Workspace, tmp_path: Path) -> None:
    write(tmp_path / "xdg" / "xqueue" / CONFIG_NAME, RETRY.format(20))

    config = load(packaged, workspace, environ={"XDG_CONFIG_HOME": str(tmp_path / "xdg")})

    assert config.worker.retry_delay_seconds == 20


def test_the_workspace_layer_beats_the_user_layer(packaged: Path, workspace: Workspace, tmp_path: Path) -> None:
    write(tmp_path / "xdg" / "xqueue" / CONFIG_NAME, RETRY.format(20))
    write(workspace.directory / CONFIG_NAME, RETRY.format(30))

    config = load(packaged, workspace, environ={"XDG_CONFIG_HOME": str(tmp_path / "xdg")})

    assert config.worker.retry_delay_seconds == 30


def test_the_environment_beats_the_workspace_layer(packaged: Path, workspace: Workspace) -> None:
    write(workspace.directory / CONFIG_NAME, RETRY.format(30))

    config = load(packaged, workspace, environ={"XQUEUE_WORKER__RETRY_DELAY_SECONDS": "40"})

    assert config.worker.retry_delay_seconds == 40


def test_an_override_beats_the_environment(packaged: Path, workspace: Workspace) -> None:
    config = load(
        packaged,
        workspace,
        inputs=ConfigInputs(overrides={"worker.retry_delay_seconds": "60"}),
        environ={"XQUEUE_WORKER__RETRY_DELAY_SECONDS": "40"},
    )

    assert config.worker.retry_delay_seconds == 60


# --- what the environment layer must not touch -----------------------------


@pytest.mark.parametrize(
    "variable",
    ["XQUEUE_HOME", "XQUEUE_ROOT", "XQUEUE_DB_PATH", "XQUEUE_LOG_LEVEL", "XQUEUE_LOG_FORMAT"],
)
def test_the_flat_variables_are_invisible_to_the_environment_layer(
    packaged: Path, workspace: Workspace, variable: str
) -> None:
    """They have no nested delimiter, so XCFG never sees them as settings."""
    config = load(packaged, workspace, environ={variable: "/somewhere"})

    assert config.paths.state_root == workspace.directory
    assert config.worker.retry_delay_seconds == 1


def test_the_config_variable_names_a_file_rather_than_a_setting(
    packaged: Path, workspace: Workspace, tmp_path: Path
) -> None:
    explicit = write(tmp_path / "from-env.yaml", RETRY.format(77))

    config = load(packaged, workspace, environ={CONFIG_ENV_VAR: str(explicit)})

    assert config.worker.retry_delay_seconds == 77


def test_the_env_variable_selects_an_overlay(packaged: Path, workspace: Workspace) -> None:
    write(packaged / "config.staging.yaml", RETRY.format(50))

    config = load(packaged, workspace, environ={ENV_NAME_VAR: "staging"})

    assert config.worker.retry_delay_seconds == 50


# --- failures ---------------------------------------------------------------


def test_an_unknown_key_is_a_configuration_error(packaged: Path, workspace: Workspace) -> None:
    """Not a pydantic ValidationError: XCFG's model is behind the adapter."""
    write(workspace.directory / CONFIG_NAME, "worker:\n  nonsense: 1\n")

    with pytest.raises(ConfigurationError) as caught:
        load(packaged, workspace)

    assert caught.value.code == "configuration_error"


def test_an_out_of_range_value_is_a_configuration_error(packaged: Path, workspace: Workspace) -> None:
    with pytest.raises(ConfigurationError):
        load(packaged, workspace, inputs=ConfigInputs(overrides={"worker.poll_interval_seconds": "0"}))


def test_a_missing_explicit_file_is_a_configuration_error(packaged: Path, workspace: Workspace, tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        load(packaged, workspace, inputs=ConfigInputs(config_path=tmp_path / "absent.yaml"))


def test_an_unknown_env_names_the_ones_that_exist(packaged: Path, workspace: Workspace) -> None:
    write(packaged / "config.staging.yaml", RETRY.format(50))

    with pytest.raises(ConfigurationError, match="staging"):
        load(packaged, workspace, inputs=ConfigInputs(env_name="production"))


# --- properties -------------------------------------------------------------


def test_resolution_does_not_depend_on_the_working_directory(
    packaged: Path, workspace: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(workspace.directory / CONFIG_NAME, RETRY.format(30))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    monkeypatch.chdir(tmp_path)
    here = load(packaged, workspace)
    monkeypatch.chdir(elsewhere)
    there = load(packaged, workspace)

    assert here == there
    assert here.worker.retry_delay_seconds == 30


def test_a_home_workspace_composes_the_same_way(packaged: Path, tmp_path: Path) -> None:
    home = Workspace(
        root=tmp_path,
        directory=tmp_path / "home-instance",
        scope=WorkspaceScope.HOME,
        marker=None,
    )
    write(home.directory / CONFIG_NAME, RETRY.format(30))

    config = load(packaged, home)

    assert config.worker.retry_delay_seconds == 30
    assert config.paths.state_root == home.directory


def test_paths_declared_in_config_win_over_the_derived_ones(
    packaged: Path, workspace: Workspace, tmp_path: Path
) -> None:
    write(workspace.directory / CONFIG_NAME, f"state_root: {tmp_path / 'elsewhere'}\n")

    config = load(packaged, workspace)

    assert config.paths.state_root == tmp_path / "elsewhere"
    # Only what was declared moves; the rest still derives from the workspace.
    assert config.paths.log_root == workspace.directory / "logs"
