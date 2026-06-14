"""
UPSC Daily Digest — Structured Logging
=======================================
JSON-structured logging with context binding via structlog.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog

_logging_configured = False


def setup_logging(log_dir: Path | None = None, level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    global _logging_configured

    # Ensure log directory exists
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

    # Configure standard logging
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_dir:
        file_handler = logging.FileHandler(
            log_dir / "digest.log", encoding="utf-8"
        )
        handlers.append(file_handler)

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=handlers,
        force=True,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        # FIX: Must be False so loggers obtained at module-import time
        # (before setup_logging() is called) get re-configured properly
        cache_logger_on_first_use=False,
    )

    _logging_configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named logger with context binding support."""
    return structlog.get_logger(name)
