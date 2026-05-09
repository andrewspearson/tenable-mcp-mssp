"""Tests for package logging configuration."""

from __future__ import annotations

import io
import logging
import os
import unittest
from unittest.mock import patch

from tenable_mcp_mssp.logging_config import (
    LOG_LEVEL_ENV,
    PACKAGE_LOGGER_NAME,
    configure_logging,
)


class LoggingConfigTests(unittest.TestCase):
    """Tests for stderr logging setup."""

    def tearDown(self) -> None:
        """Remove handlers installed during tests."""

        logger = logging.getLogger(PACKAGE_LOGGER_NAME)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        logger.addHandler(logging.NullHandler())
        logger.setLevel(logging.NOTSET)
        logger.propagate = True

    def test_default_log_level_is_warning(self) -> None:
        """Logging should default to WARNING."""

        with patch.dict(os.environ, {}, clear=True):
            level = configure_logging()

        self.assertEqual(level, logging.WARNING)
        self.assertEqual(
            logging.getLogger(PACKAGE_LOGGER_NAME).level,
            logging.WARNING,
        )

    def test_valid_log_level_is_honored(self) -> None:
        """Configured log levels should be applied."""

        with patch.dict(os.environ, {LOG_LEVEL_ENV: "debug"}, clear=True):
            level = configure_logging()

        self.assertEqual(level, logging.DEBUG)
        self.assertEqual(
            logging.getLogger(PACKAGE_LOGGER_NAME).level,
            logging.DEBUG,
        )

    def test_invalid_log_level_falls_back_to_warning(self) -> None:
        """Invalid log levels should fall back safely."""

        stderr = io.StringIO()

        with (
            patch.dict(os.environ, {LOG_LEVEL_ENV: "verbose"}, clear=True),
            patch("sys.stderr", stderr),
        ):
            level = configure_logging()

        self.assertEqual(level, logging.WARNING)
        self.assertIn("Invalid TENABLE_MCP_MSSP_LOG_LEVEL", stderr.getvalue())

    def test_logging_uses_stderr_not_stdout(self) -> None:
        """Package logs should be written to stderr."""

        stderr = io.StringIO()
        stdout = io.StringIO()

        with (
            patch.dict(os.environ, {LOG_LEVEL_ENV: "INFO"}, clear=True),
            patch("sys.stderr", stderr),
            patch("sys.stdout", stdout),
        ):
            configure_logging()
            logging.getLogger(PACKAGE_LOGGER_NAME).info("operator message")

        self.assertIn("operator message", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")

    def test_log_messages_include_timestamps(self) -> None:
        """Package logs should include an operator-friendly timestamp."""

        stderr = io.StringIO()

        with (
            patch.dict(os.environ, {LOG_LEVEL_ENV: "INFO"}, clear=True),
            patch("sys.stderr", stderr),
        ):
            configure_logging()
            logging.getLogger(PACKAGE_LOGGER_NAME).info("timestamped message")

        self.assertRegex(
            stderr.getvalue(),
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        )
        self.assertIn("timestamped message", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
