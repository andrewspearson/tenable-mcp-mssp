"""Tests for MCP server tool registration."""

from __future__ import annotations

import unittest

from simple_mcp.server import mcp


class ServerToolRegistrationTests(unittest.IsolatedAsyncioTestCase):
    """Tests for the public MCP tool surface."""

    async def test_only_expected_tools_are_registered(self) -> None:
        """The public MCP surface should expose only intended tools."""

        tools = await mcp.list_tools(run_middleware=False)

        self.assertEqual(
            [tool.name for tool in tools],
            [
                "list_mssp_child_accounts",
                "list_available_tenable_mcp_tools",
            ],
        )


if __name__ == "__main__":
    unittest.main()
