"""Tests for single-child Tenable MCP orchestration."""

from __future__ import annotations

import unittest

from simple_mcp.child_credentials import ChildCredential
from simple_mcp.single_child_tenable_mcp import list_available_tenable_mcp_tools


class SingleChildTenableMcpTests(unittest.IsolatedAsyncioTestCase):
    """Tests for single-child Tenable MCP orchestration helpers."""

    async def test_list_available_tenable_mcp_tools_uses_credentials(self) -> None:
        """Tool listing should call the official MCP lister with stored keys."""

        credential = ChildCredential(
            child_container_uuid="child-uuid",
            access_key="stored-access-key",
            secret_key="stored-secret-key",
        )
        tool_result = [
            {
                "name": "scan_list",
                "description": "List scans.",
                "input_schema": {"type": "object"},
            }
        ]
        calls: list[tuple[str, str]] = []

        async def fake_tool_lister(
            access_key: str,
            secret_key: str,
        ) -> list[dict[str, object]]:
            calls.append((access_key, secret_key))
            return tool_result

        result = await list_available_tenable_mcp_tools(
            "child-uuid",
            credential_provider=lambda child_uuid: credential,
            tool_lister=fake_tool_lister,
        )

        self.assertEqual(result, tool_result)
        self.assertEqual(calls, [("stored-access-key", "stored-secret-key")])

    async def test_list_available_tenable_mcp_tools_does_not_return_keys(
        self,
    ) -> None:
        """Public orchestration output should not include generated keys."""

        credential = ChildCredential(
            child_container_uuid="child-uuid",
            access_key="stored-access-key",
            secret_key="stored-secret-key",
        )

        async def fake_tool_lister(
            access_key: str,
            secret_key: str,
        ) -> list[dict[str, object]]:
            return [
                {
                    "name": "scan_list",
                    "description": "List scans.",
                    "input_schema": {"type": "object"},
                }
            ]

        result = await list_available_tenable_mcp_tools(
            "child-uuid",
            credential_provider=lambda child_uuid: credential,
            tool_lister=fake_tool_lister,
        )

        self.assertNotIn("access_key", result[0])
        self.assertNotIn("secret_key", result[0])


if __name__ == "__main__":
    unittest.main()
