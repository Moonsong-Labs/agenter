"""Logging configuration for agenter.

This module provides utilities to configure structlog output.
By default, the library uses debug-level structured logging.

For cleaner notebook output:
    from agenter.logging import configure_logging
    configure_logging(level="INFO")  # Only show INFO and above
    configure_logging(level="WARNING")  # Only show warnings and errors
    configure_logging(quiet=True)  # Silence all agenter logs
"""

from __future__ import annotations

import logging
from typing import Literal

import structlog


def configure_logging(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
    quiet: bool = False,
) -> None:
    """Configure agenter logging output.

    Args:
        level: Minimum log level to display. Default is INFO which hides
            verbose debug output.
        quiet: If True, silence all agenter logs completely.

    Example:
        >>> from agenter.logging import configure_logging
        >>> configure_logging(level="INFO")  # Hide debug messages
        >>> configure_logging(quiet=True)    # Silence all logs
    """
    if quiet:
        level = "CRITICAL"

    # Set level on the root logger for structlog
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level),
        force=True,
    )

    # Configure structlog with the same level
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )
