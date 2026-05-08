"""Tests for configuration loading."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tenable_mcp_mssp.config import ConfigurationError, get_settings


class GetSettingsTests(unittest.TestCase):
    """Tests for validated settings loading."""

    def test_missing_required_keys_raises_configuration_error(self) -> None:
        """Missing Tenable settings should fail before creating a client."""

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("tenable_mcp_mssp.config.load_dotenv"),
            self.assertRaisesRegex(
                ConfigurationError,
                (
                    "TENABLE_ACCESS_KEY, TENABLE_SECRET_KEY, "
                    "TENABLE_VENDOR, TENABLE_PRODUCT"
                ),
            ),
        ):
            get_settings()


if __name__ == "__main__":
    unittest.main()
