"""Logging configuration for the Tenable MCP MSSP server."""

from __future__ import annotations

import logging
import os
import sys


LOG_LEVEL_ENV = "TENABLE_MCP_MSSP_LOG_LEVEL"
DEFAULT_LOG_LEVEL = logging.WARNING
PACKAGE_LOGGER_NAME = "tenable_mcp_mssp"
_HANDLER_MARKER = "_tenable_mcp_mssp_handler"
_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging() -> int:
    """Configure package logging to stderr and return the active level."""

    level, invalid_level = _resolve_log_level(os.environ.get(LOG_LEVEL_ENV))
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    _replace_package_handler(logger, level)

    if invalid_level:
        logger.warning(
            "Invalid %s value %r; using WARNING.",
            LOG_LEVEL_ENV,
            invalid_level,
        )

    return level


def _resolve_log_level(value: str | None) -> tuple[int, str | None]:
    """Return the configured log level and invalid value when present."""

    if value is None or not value.strip():
        return DEFAULT_LOG_LEVEL, None

    clean_value = value.strip().upper()
    level = _LOG_LEVELS.get(clean_value)
    if level is None:
        return DEFAULT_LOG_LEVEL, value

    return level, None


def _replace_package_handler(logger: logging.Logger, level: int) -> None:
    """Install one package-owned stderr handler."""

    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    setattr(handler, _HANDLER_MARKER, True)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logger.addHandler(handler)
