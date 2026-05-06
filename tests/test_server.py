"""Tests for MCP server tool wrappers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from simple_mcp.server import generate_child_api_keys


class ServerToolTests(unittest.TestCase):
    """Tests for public MCP tool behavior."""

    def test_generate_child_api_keys_stores_and_returns_safe_metadata(self) -> None:
        """The public tool should not return generated secrets."""

        raw_response = {
            "parent_container_uuid": "parent-uuid",
            "child_container_uuid": "child-uuid",
            "child_container_site": "us-2b",
            "access_key": "generated-access-key",
            "secret_key": "generated-secret-key",
            "keys_expiration_epoch_seconds": 2_000,
            "remote": False,
        }
        safe_metadata = {
            "parent_container_uuid": "parent-uuid",
            "child_container_uuid": "child-uuid",
            "child_container_site": "us-2b",
            "keys_expiration_epoch_seconds": 2_000,
            "remote": False,
            "stored": True,
        }

        with (
            patch("simple_mcp.server.generate_keys", return_value=raw_response),
            patch(
                "simple_mcp.server.store_child_credentials",
                return_value=safe_metadata,
            ) as store_credentials,
        ):
            result = generate_child_api_keys("child-uuid", 60)

        store_credentials.assert_called_once_with(raw_response)
        self.assertEqual(result, safe_metadata)
        self.assertNotIn("access_key", result)
        self.assertNotIn("secret_key", result)


if __name__ == "__main__":
    unittest.main()
