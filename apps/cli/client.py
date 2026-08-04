"""The CLI channel's single client construction site."""

from __future__ import annotations

from pathlib import Path

from xqueue import ConfigInputs, Xqueue
from xqueue.core.errors import ValidationError


def parse_overrides(values: list[str]) -> dict[str, str]:
    """Turn repeated `--set path=value` into a mapping.

    Splitting on the first `=` only, so a value may contain one.
    """
    overrides: dict[str, str] = {}
    for value in values:
        path, separator, assigned = value.partition("=")
        if not separator or not path.strip():
            raise ValidationError(
                f"--set expects PATH=VALUE, got {value!r}",
                details={"value": value},
            )
        overrides[path.strip()] = assigned
    return overrides


_config_inputs = ConfigInputs()


def set_config_inputs(inputs: ConfigInputs) -> None:
    """Record the `--config`, `--env`, and `--set` values for this invocation.

    Called once by the root callback. Module state rather than the click
    context, because the context is not reachable without importing click, and
    the CLI cannot import click: Typer vendored it in 0.27, so a real `click`
    is either absent from an installed `xqueue[cli]` or -- worse -- present and
    keeping a *different* context stack from the one Typer pushes onto.

    A process runs one invocation, so one value is all there is to hold.
    """
    global _config_inputs
    _config_inputs = inputs


def current_config_inputs() -> ConfigInputs:
    """The values recorded by the root callback, or empty ones."""
    return _config_inputs


def open_client(
    *,
    use_workspace_instance: bool = False,
    config_path: Path | None = None,
    workspace_root: Path | None = None,
) -> Xqueue:
    """Open one client for the current workspace.

    Every command opens its client here, so a change to how the CLI resolves a
    workspace root or a config path is a one-file change. This module stays a
    leaf: presentation modules import it, and it imports nothing from them.

    `workspace_root` is where discovery *starts*; the resolver walks upward from
    it and falls back to the home instance. `use_workspace_instance` pins that
    root instead, skipping both. It is the deprecated spelling kept for
    `--workspace-instance`, and it now means `<root>/.xqueue` rather than the
    old `<root>/instance`.

    A command-level `config_path` wins over the root `--config`, because it is
    the more specific of the two.
    """
    inputs = current_config_inputs()
    if config_path is not None:
        inputs = ConfigInputs(
            config_path=config_path,
            env_name=inputs.env_name,
            overrides=inputs.overrides,
        )
    return Xqueue.open(
        config_path=inputs.config_path,
        env_name=inputs.env_name,
        overrides=inputs.overrides,
        workspace_root=workspace_root or Path.cwd(),
        use_workspace_instance=use_workspace_instance,
    )
