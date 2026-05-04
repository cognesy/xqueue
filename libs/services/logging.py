"""Shared structured logging configuration."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import logging
import os
import sys
from typing import Any

import structlog
import yaml

from xqueue_libs.services.resources import resource_file

LOG_LEVEL_ENV = "XQUEUE_LOG_LEVEL"
LOG_FORMAT_ENV = "XQUEUE_LOG_FORMAT"

_CONFIGURED = False
_CONFIGURED_STREAM_ID: int | None = None
_CONFIGURED_LEVEL_NAME: str | None = None
_CONFIGURED_FORMAT: str | None = None
_CONFIGURED_CONFIG: LoggingConfig | None = None


@dataclass(frozen=True)
class LoggingEventsConfig:
    """Event families controlled by logging configuration."""

    actions: bool = True
    workers: bool = True
    controller: bool = True
    jobs: bool = True
    subprocesses: bool = True


@dataclass(frozen=True)
class LoggingFieldsConfig:
    """Structured log field policy."""

    include: tuple[str, ...] = ()
    redact: tuple[str, ...] = ("token", "secret", "credential", "env")


@dataclass(frozen=True)
class LoggingConfig:
    """Process logging configuration loaded from resources."""

    version: int = 1
    logger: str = "xqueue"
    destination: str = "stderr"
    format: str = "json"
    level: str = "INFO"
    timestamp: str = "iso"
    events: LoggingEventsConfig = field(default_factory=LoggingEventsConfig)
    fields: LoggingFieldsConfig = field(default_factory=LoggingFieldsConfig)


DEFAULT_LOGGING_CONFIG = LoggingConfig()


def default_logging_config_path():
    """Return the packaged default logging config resource."""

    return resource_file("logging", "default.yaml")


def load_logging_config(*, apply_env: bool = True) -> LoggingConfig:
    """Load checked-in logging config, optionally applying environment overrides."""

    path = default_logging_config_path()
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"logging config must be a mapping: {path}")

    config = _parse_logging_config(payload)
    if apply_env:
        config = apply_logging_env_overrides(config)
        _validate_logging_config(config)
    return config


def apply_logging_env_overrides(config: LoggingConfig) -> LoggingConfig:
    """Apply supported environment overrides to one logging config."""

    level = os.environ.get(LOG_LEVEL_ENV)
    log_format = os.environ.get(LOG_FORMAT_ENV)
    if level is not None:
        config = replace(config, level=level.strip().upper())
    if log_format is not None:
        config = replace(config, format=log_format.strip().lower())
    return config


def configure_logging(level: str | None = None) -> LoggingConfig:
    """Configure structlog and stdlib logging once for the current process."""
    global _CONFIGURED, _CONFIGURED_CONFIG, _CONFIGURED_FORMAT
    global _CONFIGURED_LEVEL_NAME, _CONFIGURED_STREAM_ID

    config = load_logging_config()
    if level is not None:
        config = replace(config, level=level.upper())
        _validate_logging_config(config)

    level_name = config.level
    level_value = getattr(logging, level_name, logging.INFO)
    log_format = config.format
    stream_id = id(sys.stderr)
    if (
        _CONFIGURED
        and _CONFIGURED_CONFIG == config
        and _CONFIGURED_LEVEL_NAME == level_name
        and _CONFIGURED_FORMAT == log_format
        and _CONFIGURED_STREAM_ID == stream_id
    ):
        return config

    renderer: structlog.typing.Processor
    if log_format == "json" or (log_format == "auto" and not sys.stderr.isatty()):
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    logging.basicConfig(
        format="%(message)s",
        level=level_value,
        stream=sys.stderr,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt=config.timestamp, utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        wrapper_class=structlog.make_filtering_bound_logger(level_value),
        cache_logger_on_first_use=False,
    )

    _CONFIGURED = True
    _CONFIGURED_CONFIG = config
    _CONFIGURED_LEVEL_NAME = level_name
    _CONFIGURED_FORMAT = log_format
    _CONFIGURED_STREAM_ID = stream_id
    return config


def _parse_logging_config(payload: dict[str, Any]) -> LoggingConfig:
    events = payload.get("events", {})
    fields = payload.get("fields", {})
    if not isinstance(events, dict):
        raise ValueError("logging config events must be a mapping")
    if not isinstance(fields, dict):
        raise ValueError("logging config fields must be a mapping")

    config = LoggingConfig(
        version=int(payload.get("version", DEFAULT_LOGGING_CONFIG.version)),
        logger=str(payload.get("logger", DEFAULT_LOGGING_CONFIG.logger)),
        destination=str(payload.get("destination", DEFAULT_LOGGING_CONFIG.destination)).lower(),
        format=str(payload.get("format", DEFAULT_LOGGING_CONFIG.format)).lower(),
        level=str(payload.get("level", DEFAULT_LOGGING_CONFIG.level)).upper(),
        timestamp=str(payload.get("timestamp", DEFAULT_LOGGING_CONFIG.timestamp)).lower(),
        events=LoggingEventsConfig(
            actions=bool(events.get("actions", DEFAULT_LOGGING_CONFIG.events.actions)),
            workers=bool(events.get("workers", DEFAULT_LOGGING_CONFIG.events.workers)),
            controller=bool(events.get("controller", DEFAULT_LOGGING_CONFIG.events.controller)),
            jobs=bool(events.get("jobs", DEFAULT_LOGGING_CONFIG.events.jobs)),
            subprocesses=bool(events.get("subprocesses", DEFAULT_LOGGING_CONFIG.events.subprocesses)),
        ),
        fields=LoggingFieldsConfig(
            include=_string_tuple(fields.get("include", DEFAULT_LOGGING_CONFIG.fields.include)),
            redact=_string_tuple(fields.get("redact", DEFAULT_LOGGING_CONFIG.fields.redact)),
        ),
    )
    _validate_logging_config(config)
    return config


def _validate_logging_config(config: LoggingConfig) -> None:
    if config.version != 1:
        raise ValueError(f"unsupported logging config version: {config.version}")
    if config.destination != "stderr":
        raise ValueError(f"unsupported logging destination: {config.destination}")
    if config.format not in {"auto", "json", "console"}:
        raise ValueError(f"unsupported logging format: {config.format}")
    if config.timestamp != "iso":
        raise ValueError(f"unsupported logging timestamp: {config.timestamp}")


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        raise ValueError("logging config field lists must be lists of strings")
    return tuple(str(item) for item in value)
