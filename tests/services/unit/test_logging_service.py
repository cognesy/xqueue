from __future__ import annotations

import json

import structlog

from libs.services.logging import default_logging_config_path, load_logging_config
import libs.services.logging as xqueue_logging


def _reset_logging() -> None:
    xqueue_logging._CONFIGURED = False
    xqueue_logging._CONFIGURED_STREAM_ID = None
    xqueue_logging._CONFIGURED_LEVEL_NAME = None
    xqueue_logging._CONFIGURED_FORMAT = None
    xqueue_logging._CONFIGURED_CONFIG = None
    structlog.reset_defaults()


def test_default_logging_config_loads() -> None:
    config = load_logging_config(apply_env=False)

    assert default_logging_config_path().exists()
    assert config.logger == "xqueue"
    assert config.destination == "stderr"
    assert config.format == "json"
    assert config.level == "INFO"
    assert config.events.actions is True
    assert config.events.workers is True
    assert config.events.controller is True
    assert config.events.jobs is True
    assert config.events.subprocesses is True
    assert "controller_id" in config.fields.include
    assert "secret" in config.fields.redact


def test_logging_env_overrides_default_config(monkeypatch) -> None:
    monkeypatch.setenv("XQUEUE_LOG_LEVEL", "warning")
    monkeypatch.setenv("XQUEUE_LOG_FORMAT", "console")

    config = load_logging_config()

    assert config.level == "WARNING"
    assert config.format == "console"


def test_configured_logger_writes_json_to_stderr(capsys, monkeypatch) -> None:
    monkeypatch.setenv("XQUEUE_LOG_LEVEL", "INFO")
    monkeypatch.setenv("XQUEUE_LOG_FORMAT", "json")
    _reset_logging()

    xqueue_logging.configure_logging()
    structlog.get_logger("xqueue.test").info("logging_contract_check")
    captured = capsys.readouterr()

    assert captured.out == ""
    payload = json.loads(captured.err.splitlines()[-1])
    assert payload["event"] == "logging_contract_check"
    assert payload["level"] == "info"
