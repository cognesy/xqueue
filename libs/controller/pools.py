"""Structured mutation adapter for xqueue-owned controller pool config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError
from xqueue.controller.models import ControllerPoolConfigView, ControllerPoolMutationResult
from xqueue.core.errors import ValidationError
from xqueue.workspace.models import ControllerPoolConfig, RestartPolicy
from xqueue.workspace.settings import Settings


class ControllerPoolConfigService:
    """Read and mutate only xqueue-owned controller pool configuration."""

    def list_pools(self, *, config_path: Path) -> list[ControllerPoolConfigView]:
        raw = self._load_raw(config_path)
        config = self._validate_static(raw, config_path=config_path)
        return [_pool_view(name, pool) for name, pool in sorted(config.controller.pools.items())]

    def ensure_pool(
        self,
        *,
        config_path: Path,
        name: str,
        queues: list[str],
        concurrency: int,
        poll_interval_seconds: float | None = None,
        lease_seconds: int = 30,
        restart_policy: RestartPolicy = RestartPolicy.ON_FAILURE,
        default_timeout_seconds: int | None = None,
    ) -> ControllerPoolMutationResult:
        _validate_name(name, field="pool")
        for queue in queues:
            _validate_name(queue, field="queue")
        desired = ControllerPoolConfig(
            queues=queues,
            concurrency=concurrency,
            poll_interval_seconds=poll_interval_seconds,
            lease_seconds=lease_seconds,
            restart_policy=restart_policy,
            default_timeout_seconds=default_timeout_seconds,
        )
        raw = self._load_raw(config_path)
        self._validate_static(raw, config_path=config_path)
        pools = _raw_pools(raw)
        existing = pools.get(name)
        desired_payload = desired.model_dump(mode="json", exclude_none=True)
        if existing == desired_payload:
            return _mutation(
                action="noop",
                name=name,
                pool=_pool_view(name, desired),
                config_path=config_path,
                restart_required=False,
            )

        pools[name] = desired_payload
        self._validate_static(raw, config_path=config_path)
        self._save_raw(config_path, raw)
        return _mutation(
            action="created" if existing is None else "updated",
            name=name,
            pool=_pool_view(name, desired),
            config_path=config_path,
            restart_required=True,
        )

    def remove_pool(self, *, config_path: Path, name: str) -> ControllerPoolMutationResult:
        _validate_name(name, field="pool")
        raw = self._load_raw(config_path)
        self._validate_static(raw, config_path=config_path)
        pools = _raw_pools(raw)
        existing = pools.pop(name, None)
        if existing is None:
            return _mutation(
                action="noop",
                name=name,
                pool=None,
                config_path=config_path,
                restart_required=False,
            )

        self._validate_static(raw, config_path=config_path)
        self._save_raw(config_path, raw)
        return _mutation(
            action="removed",
            name=name,
            pool=None,
            config_path=config_path,
            restart_required=True,
        )

    def _load_raw(self, config_path: Path) -> dict[str, Any]:
        if not config_path.exists():
            return {}
        loaded = yaml.safe_load(config_path.read_text()) or {}
        if not isinstance(loaded, dict):
            raise ValidationError(
                "configuration file must contain a mapping",
                details={"config_path": str(config_path)},
            )
        return loaded

    def _validate_static(self, raw: dict[str, Any], *, config_path: Path) -> Settings:
        try:
            return Settings.model_validate(raw)
        except PydanticValidationError as exc:
            raise ValidationError(
                "invalid xqueue configuration",
                details={"config_path": str(config_path), "errors": exc.errors()},
            ) from exc

    def _save_raw(self, config_path: Path, raw: dict[str, Any]) -> None:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(raw, sort_keys=False))


def _raw_pools(raw: dict[str, Any]) -> dict[str, Any]:
    controller = raw.setdefault("controller", {})
    if not isinstance(controller, dict):
        raise ValidationError("controller config must be a mapping")
    pools = controller.setdefault("pools", {})
    if not isinstance(pools, dict):
        raise ValidationError("controller.pools config must be a mapping")
    return pools


def _pool_view(name: str, pool: ControllerPoolConfig) -> ControllerPoolConfigView:
    return ControllerPoolConfigView(
        name=name,
        queues=list(pool.queues),
        concurrency=pool.concurrency,
        poll_interval_seconds=pool.poll_interval_seconds,
        lease_seconds=pool.lease_seconds,
        restart_policy=pool.restart_policy.value,
        default_timeout_seconds=pool.default_timeout_seconds,
    )


def _mutation(
    *,
    action: str,
    name: str,
    pool: ControllerPoolConfigView | None,
    config_path: Path,
    restart_required: bool,
) -> ControllerPoolMutationResult:
    return ControllerPoolMutationResult(
        action=action,
        name=name,
        pool=pool,
        config_path=str(config_path),
        restart_required=restart_required,
    )


def _validate_name(value: str, *, field: str) -> None:
    if not value or value.strip() != value or any(character.isspace() for character in value):
        raise ValidationError(
            f"{field} name must be non-empty and contain no whitespace",
            details={field: value},
        )
