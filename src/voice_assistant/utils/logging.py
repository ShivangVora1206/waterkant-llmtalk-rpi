"""Structured logging setup using structlog."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

import structlog

LOG_DIR = Path(__file__).parent.parent.parent.parent / "data" / "logs"


def configure_logging(log_level: str = "INFO") -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "app.log"

    level = getattr(logging, log_level.upper(), logging.INFO)

    rotating = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=3
    )
    rotating.setLevel(level)

    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(level)

    logging.basicConfig(
        level=level,
        handlers=[rotating, stream],
        format="%(message)s",
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
