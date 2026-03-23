"""Configuration loading and platform-aware path resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from platformdirs import PlatformDirs

from libs.domain.config import EffectiveConfig, RuntimePaths, StaticConfig


class ConfigLoader:
    """Loads static YAML config and resolves runtime paths."""

    def __init__(
        self,
        app_name: str = "xqueue",
        app_author: str = "xqueue",
    ) -> None:
        self._app_name = app_name
        self._app_author = app_author

    def resolve_paths(
        self,
        *,
        config_path: Path | None = None,
        workspace_root: Path | None = None,
        use_workspace_instance: bool = False,
    ) -> RuntimePaths:
        """Resolve runtime paths for either normal installs or local repo runs."""
        if use_workspace_instance:
            if workspace_root is None:
                raise ValueError("workspace_root is required when use_workspace_instance=True")
            instance_root = workspace_root / "instance"
            return RuntimePaths(
                config_file=config_path or instance_root / "config.yaml",
                state_root=instance_root,
                runtime_root=instance_root / "run",
                log_root=instance_root / "logs",
                database_path=instance_root / "xqueue.db",
            )

        dirs = PlatformDirs(appname=self._app_name, appauthor=self._app_author, roaming=False)
        state_root = Path(dirs.user_state_path)
        return RuntimePaths(
            config_file=config_path or Path(dirs.user_config_path) / "config.yaml",
            state_root=state_root,
            runtime_root=Path(dirs.user_runtime_path),
            log_root=Path(dirs.user_log_path),
            database_path=state_root / "xqueue.db",
        )

    def load(
        self,
        *,
        config_path: Path | None = None,
        workspace_root: Path | None = None,
        use_workspace_instance: bool = False,
    ) -> EffectiveConfig:
        """Load static configuration and merge it with resolved default paths."""
        default_paths = self.resolve_paths(
            config_path=config_path,
            workspace_root=workspace_root,
            use_workspace_instance=use_workspace_instance,
        )

        static_config = self._load_static(default_paths.config_file)

        state_root = static_config.state_root or default_paths.state_root
        log_root = static_config.log_root or default_paths.log_root
        runtime_root = static_config.runtime_root or default_paths.runtime_root
        database_path = static_config.database_path or default_paths.database_path

        effective_paths = RuntimePaths(
            config_file=default_paths.config_file,
            state_root=state_root,
            runtime_root=runtime_root,
            log_root=log_root,
            database_path=database_path,
        )

        return EffectiveConfig(
            paths=effective_paths,
            queue=static_config.queue,
            worker=static_config.worker,
            controller=static_config.controller,
        )

    def _load_static(self, config_file: Path) -> StaticConfig:
        """Load optional YAML configuration from disk."""
        if not config_file.exists():
            return StaticConfig()

        loaded: Any = yaml.safe_load(config_file.read_text()) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Configuration file {config_file} must contain a mapping")
        return StaticConfig.model_validate(loaded)
