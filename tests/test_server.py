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
                "run_tenable_mcp_tool_for_child",
                "run_tenable_mcp_recipe_for_child",
                "run_tenable_mcp_recipe_across_child_containers",
            ],
        )

    async def test_multi_child_runner_does_not_expose_operational_limits(
        self,
    ) -> None:
        """Concurrency and timeout controls should remain internal settings."""

        tools = await mcp.list_tools(run_middleware=False)
        fan_out_tool = next(
            tool
            for tool in tools
            if tool.name == "run_tenable_mcp_recipe_across_child_containers"
        )

        properties = fan_out_tool.parameters["properties"]

        self.assertIn("child_container_uuids", properties)
        self.assertIn("recipe", properties)
        self.assertIn("required_license", properties)
        self.assertNotIn("max_concurrency", properties)
        self.assertNotIn("child_timeout_seconds", properties)


if __name__ == "__main__":
    unittest.main()
