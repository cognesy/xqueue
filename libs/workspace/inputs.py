"""What a caller says about configuration at the moment it opens a client.

Three fields that always travel together, from `--config`, `--env`, and
repeatable `--set` on the CLI, or from the matching `Xqueue.open` arguments.
Bundling them means the runtime can keep them and recompose from exactly the
same inputs on reload, instead of each layer growing three more parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ConfigInputs:
    """Invocation-level configuration inputs. Empty is the normal case."""

    #: A file that replaces the packaged base outright.
    config_path: Path | None = None
    #: Selects a packaged `config.<name>.yaml` overlay.
    env_name: str | None = None
    #: Dotted paths to values, the last layer of all.
    overrides: dict[str, str] = field(default_factory=dict)


#: The "caller said nothing" case, so call sites need no `or ConfigInputs()`.
NO_CONFIG_INPUTS = ConfigInputs()

__all__ = ["NO_CONFIG_INPUTS", "ConfigInputs"]
