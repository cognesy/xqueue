"""Shared structured logging configuration."""

from __future__ import annotations

import logging
import sys

import structlog


_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog and stdlib logging once for the current process."""
    global _configured
    if _configured:
        return

    level_name = level.upper()
    level_value = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        level=level_value,
        stream=sys.stderr,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    _configured = True
