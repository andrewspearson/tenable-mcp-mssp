"""Tests for configuration loading."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tenable_mcp_mssp import __version__
from tenable_mcp_mssp.config import (
    ConfigurationError,
    INTEGRATION_PRODUCT,
    INTEGRATION_VENDOR,
    get_settings,
    load_dotenv,
)


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
                    "TENABLE_MSSP_PORTAL_ACCESS_KEY, "
                    "TENABLE_MSSP_PORTAL_SECRET_KEY"
                ),
            ),
        ):
            get_settings()

    def test_get_settings_loads_required_credentials(self) -> None:
        """Required MSSP Portal credentials should load from the environment."""

        with (
            patch.dict(
                os.environ,
                {
                    "TENABLE_MSSP_PORTAL_ACCESS_KEY": "access-key",
                    "TENABLE_MSSP_PORTAL_SECRET_KEY": "secret-key",
                },
                clear=True,
            ),
            patch("tenable_mcp_mssp.config.load_dotenv"),
        ):
            settings = get_settings()

        self.assertEqual(settings.mssp_portal_access_key, "access-key")
        self.assertEqual(settings.mssp_portal_secret_key, "secret-key")

    def test_get_settings_uses_hardcoded_integration_metadata(self) -> None:
        """Integration metadata should not depend on environment variables."""

        with (
            patch.dict(
                os.environ,
                {
                    "TENABLE_MSSP_PORTAL_ACCESS_KEY": "access-key",
                    "TENABLE_MSSP_PORTAL_SECRET_KEY": "secret-key",
                    "TENABLE_MCP_MSSP_VENDOR": "ignored-vendor",
                    "TENABLE_MCP_MSSP_PRODUCT": "ignored-product",
                    "TENABLE_MCP_MSSP_BUILD": "ignored-build",
                },
                clear=True,
            ),
            patch("tenable_mcp_mssp.config.load_dotenv"),
        ):
            settings = get_settings()

        self.assertEqual(settings.tenable_vendor, INTEGRATION_VENDOR)
        self.assertEqual(settings.tenable_product, INTEGRATION_PRODUCT)
        self.assertEqual(settings.tenable_build, __version__)

    def test_environment_overrides_dotenv_values(self) -> None:
        """.env should not overwrite values that already exist."""

        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "TENABLE_MSSP_PORTAL_ACCESS_KEY=dotenv-access",
                        "TENABLE_MSSP_PORTAL_SECRET_KEY=dotenv-secret",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {"TENABLE_MSSP_PORTAL_ACCESS_KEY": "real-access"},
                clear=True,
            ):
                load_dotenv(env_file)

                self.assertEqual(
                    os.environ["TENABLE_MSSP_PORTAL_ACCESS_KEY"],
                    "real-access",
                )
                self.assertEqual(
                    os.environ["TENABLE_MSSP_PORTAL_SECRET_KEY"],
                    "dotenv-secret",
                )


if __name__ == "__main__":
    unittest.main()
