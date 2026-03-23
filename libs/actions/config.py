"""Actions related to static configuration inspection."""

from __future__ import annotations

from pathlib import Path

from libs.actions.logging import log_action
from libs.domain.config import EffectiveConfig
from libs.services.config import ConfigLoader


class ShowConfigAction:
    """Return the effective xqueue configuration."""

    def __init__(self, loader: ConfigLoader) -> None:
        self._loader = loader

    @log_action(
        "show_config",
        context_getter=lambda self, **kwargs: {
            "use_workspace_instance": kwargs.get("use_workspace_instance", False),
            "has_config_path": kwargs.get("config_path") is not None,
        },
    )
    def __call__(
        self,
        *,
        config_path: Path | None = None,
        workspace_root: Path | None = None,
        use_workspace_instance: bool = False,
    ) -> EffectiveConfig:
        return self._loader.load(
            config_path=config_path,
            workspace_root=workspace_root,
            use_workspace_instance=use_workspace_instance,
        )
