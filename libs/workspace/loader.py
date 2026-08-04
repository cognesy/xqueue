"""The one module in xqueue that imports XCFG.

Everything about layered configuration lives behind this adapter: no `xcfg`
symbol appears in an xqueue signature, a result model, or a raised type. If
xqueue ever changes configuration libraries, this file is the change.

The precedence contract, base first:

    --config <path> / XQUEUE_CONFIG_PATH     replaces the base outright
    --env <name> / XQUEUE_ENV                config.<name>.yaml over the default
    packaged config.default.yaml             the base when neither is given

then merged over it, later winning:

    ~/.config/xqueue/config.yaml
    <workspace>/.xqueue/config.yaml
    XQUEUE_<SECTION>__<KEY>
    --set <path>=<value>

Note what the environment layer does *not* touch. XCFG only reads variables
containing the nested delimiter, so `XQUEUE_HOME`, `XQUEUE_ROOT`,
`XQUEUE_DB_PATH`, `XQUEUE_LOG_LEVEL`, and `XQUEUE_LOG_FORMAT` remain invisible
to it and keep the meanings they already had.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from xcfg import ConfigError, ConfigLoader, ConfigSpec
from xqueue.core.errors import ConfigurationError
from xqueue.runtime.resources import resource_path
from xqueue.workspace.inputs import NO_CONFIG_INPUTS, ConfigInputs
from xqueue.workspace.models import ConfigLayer, EffectiveConfig, RuntimePaths
from xqueue.workspace.paths import Workspace, derive_runtime_paths
from xqueue.workspace.settings import Settings

#: Filename used for the packaged, user, and workspace layers alike.
CONFIG_NAME = "config.yaml"

#: Prefix for environment overrides: `XQUEUE_WORKER__RETRY_DELAY_SECONDS`.
ENV_PREFIX = "XQUEUE_"

#: Names a config file outright. This is the variable the launchd and systemd
#: artifacts already set, so honouring it here is what finally makes those
#: units read the config they were pointed at.
CONFIG_ENV_VAR = "XQUEUE_CONFIG_PATH"

#: Selects a packaged `config.<name>.yaml` overlay.
ENV_NAME_VAR = "XQUEUE_ENV"

#: XDG application name for `~/.config/xqueue/config.yaml`.
APP_NAME = "xqueue"


def build_spec(config_root: Path) -> ConfigSpec:
    """xqueue's configuration shape, given where its packaged files landed.

    `project_dir` is deliberately empty: xqueue resolves its own workspace and
    passes the file directly, so XCFG must not walk the tree a second time and
    possibly land somewhere else.

    `profiled_sections` is empty too. xqueue has one backend and one storage
    engine, so a profile directory would be a mechanism with nothing to select.
    """
    return ConfigSpec(
        config_root=config_root,
        config_name=CONFIG_NAME,
        env_prefix=ENV_PREFIX,
        config_env_var=CONFIG_ENV_VAR,
        env_name_var=ENV_NAME_VAR,
        app_name=APP_NAME,
        env_extends_default=True,
    )


class SettingsLoader:
    """Composes and validates configuration for one decided workspace.

    A workspace is passed in and never rediscovered, so two clients on two
    workspaces compose independently in one process.

    `config_root` names where the packaged layer lives. It defaults to the
    installed `xqueue_resources/config`, and exists so the packaged layers can
    be exercised without writing into an installed package.
    """

    def __init__(self, *, config_root: Path | None = None) -> None:
        self._config_root = config_root

    def load(
        self,
        workspace: Workspace,
        *,
        inputs: ConfigInputs = NO_CONFIG_INPUTS,
        environ: Mapping[str, str] | None = None,
    ) -> EffectiveConfig:
        """Compose every layer, then derive paths from the result."""
        env = os.environ if environ is None else environ
        settings, spec = self._compose(workspace, inputs=inputs, environ=env)
        paths = self._paths(workspace, settings, config_path=inputs.config_path)
        return EffectiveConfig(
            paths=paths,
            queue=settings.queue,
            worker=settings.worker,
            controller=settings.controller,
            layers=self._layers(workspace, spec, inputs=inputs, environ=env),
        )

    def _compose(
        self,
        workspace: Workspace,
        *,
        inputs: ConfigInputs,
        environ: Mapping[str, str],
    ) -> tuple[Settings, ConfigSpec]:
        with self._config_root_path() as config_root:
            spec = build_spec(config_root)
            try:
                settings = ConfigLoader(spec, Settings).load(
                    config_path=inputs.config_path,
                    env_name=inputs.env_name,
                    overrides=inputs.overrides,
                    environ=environ,
                    project_path=self._workspace_config(workspace),
                )
            except ConfigError as exc:
                # The boundary: every way configuration can go wrong -- a
                # missing named file, an unknown env, an unknown key, a value
                # that fails validation -- reaches callers as one xqueue error.
                raise ConfigurationError(str(exc)) from exc
        return settings, spec

    @contextmanager
    def _config_root_path(self) -> Iterator[Path]:
        if self._config_root is not None:
            yield self._config_root
            return
        with resource_path("config") as path:
            yield path

    def _paths(
        self,
        workspace: Workspace,
        settings: Settings,
        *,
        config_path: Path | None,
    ) -> RuntimePaths:
        derived = derive_runtime_paths(workspace, config_file=config_path)
        return RuntimePaths(
            config_file=derived.config_file,
            state_root=settings.state_root or derived.state_root,
            runtime_root=settings.runtime_root or derived.runtime_root,
            log_root=settings.log_root or derived.log_root,
            database_path=settings.database_path or derived.database_path,
        )

    def _workspace_config(self, workspace: Workspace) -> Path:
        return workspace.directory / CONFIG_NAME

    def _layers(
        self,
        workspace: Workspace,
        spec: ConfigSpec,
        *,
        inputs: ConfigInputs,
        environ: Mapping[str, str],
    ) -> list[ConfigLayer]:
        """The chain that produced this configuration, base first.

        Only existence is answered here, and every name is read off the spec
        XCFG was given, so this cannot drift from the composition above.
        """
        explicit = inputs.config_path or self._named_path(environ.get(CONFIG_ENV_VAR))
        selected_env = inputs.env_name or environ.get(ENV_NAME_VAR) or ""

        layers = [
            ConfigLayer(
                layer="packaged-default",
                origin=str(spec.default_config_path),
                # An explicit file replaces the base rather than layering over it.
                applied=explicit is None and spec.default_config_path.is_file(),
            )
        ]
        if selected_env:
            layers.append(
                ConfigLayer(
                    layer="env-overlay",
                    origin=str(spec.env_config_path(selected_env)),
                    applied=explicit is None,
                )
            )
        if explicit is not None:
            layers.append(ConfigLayer(layer="explicit-file", origin=str(explicit), applied=True))

        user = self._user_config(spec, environ)
        layers.append(ConfigLayer(layer="user", origin=str(user), applied=user.is_file()))

        workspace_config = self._workspace_config(workspace)
        layers.append(
            ConfigLayer(
                layer="workspace",
                origin=str(workspace_config),
                applied=workspace_config.is_file(),
            )
        )

        environment = sorted(self._environment_keys(spec, environ))
        layers.append(
            ConfigLayer(
                layer="environment",
                origin=", ".join(environment) or f"{ENV_PREFIX}<SECTION>__<KEY>",
                applied=bool(environment),
            )
        )
        layers.append(
            ConfigLayer(
                layer="override",
                origin=", ".join(sorted(inputs.overrides)) or "--set <path>=<value>",
                applied=bool(inputs.overrides),
            )
        )
        return layers

    def _named_path(self, value: str | None) -> Path | None:
        return Path(value).expanduser() if value else None

    def _user_config(self, spec: ConfigSpec, environ: Mapping[str, str]) -> Path:
        base = environ.get("XDG_CONFIG_HOME")
        root = Path(base).expanduser() if base else Path.home() / ".config"
        return root / spec.app_name / spec.config_name

    def _environment_keys(self, spec: ConfigSpec, environ: Mapping[str, str]) -> list[str]:
        delimiter = spec.env_nested_delimiter
        reserved = {spec.explicit_config_var, spec.env_selector_var}
        return [
            key
            for key in environ
            if key.startswith(ENV_PREFIX) and key not in reserved and delimiter in key[len(ENV_PREFIX) :]
        ]


__all__ = ["CONFIG_ENV_VAR", "CONFIG_NAME", "SettingsLoader", "build_spec"]
