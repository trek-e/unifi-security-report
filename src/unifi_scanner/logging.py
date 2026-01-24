"""Structured logging configuration for UniFi Scanner."""

from __future__ import annotations

import logging
import sys
from typing import List, Literal

import structlog


def configure_logging(
    log_format: Literal["json", "text"] = "json",
    log_level: str = "INFO",
) -> None:
    """Configure structlog for the application.

    Args:
        log_format: Output format - "json" for production, "text" for development.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
    """
    # Common processors for all formats
    shared_processors: List[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "json":
        # Production: JSON output
        processors: List[structlog.typing.Processor] = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: colored console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to route through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def get_logger() -> structlog.stdlib.BoundLogger:
    """Get a configured structlog logger instance."""
    return structlog.get_logger()
