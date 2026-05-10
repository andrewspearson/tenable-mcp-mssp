"""Tests for MCP server tool registration."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tenable_mcp_mssp import server


mcp = server.mcp


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
                "get_child_container_scope",
                "run_tenable_mcp_tool_for_child",
                "run_tenable_mcp_recipe_for_child",
                "run_tenable_mcp_recipe_across_child_containers",
                "bulk_vm_cve_query",
                "get_bulk_vm_cve_query_status",
                "get_bulk_vm_cve_query_result",
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
        self.assertNotIn("required_license", properties)
        self.assertNotIn("ctx", properties)
        self.assertNotIn("max_concurrency", properties)
        self.assertNotIn("child_timeout_seconds", properties)

    async def test_bulk_query_tools_expose_expected_parameters(self) -> None:
        """Bulk query tools should expose only the intended public inputs."""

        tools = await mcp.list_tools(run_middleware=False)
        bulk_tool = next(
            tool for tool in tools if tool.name == "bulk_vm_cve_query"
        )
        status_tool = next(
            tool for tool in tools if tool.name == "get_bulk_vm_cve_query_status"
        )
        result_tool = next(
            tool for tool in tools if tool.name == "get_bulk_vm_cve_query_result"
        )

        self.assertEqual(
            list(bulk_tool.parameters["properties"]),
            ["cve_ids"],
        )
        self.assertEqual(
            list(status_tool.parameters["properties"]),
            ["run_id"],
        )
        self.assertEqual(
            list(result_tool.parameters["properties"]),
            ["run_id"],
        )

    async def test_public_multi_child_runner_does_not_pass_license_filter(
        self,
    ) -> None:
        """The public wrapper should not let agents supply license filters."""

        async def fake_runner(
            child_container_uuids: list[str],
            recipe: list[dict[str, object]],
            **kwargs: object,
        ) -> dict[str, object]:
            self.assertEqual(child_container_uuids, ["child-1"])
            self.assertEqual(recipe, [{"tool_name": "tool"}])
            self.assertNotIn("required_license", kwargs)
            return {
                "queued": 1,
                "succeeded": 1,
                "failed": 0,
                "skipped": 0,
                "children": [],
            }

        with patch.object(server, "run_recipe_across_children", fake_runner):
            result = await server.run_tenable_mcp_recipe_across_child_containers(
                ["child-1"],
                [{"tool_name": "tool"}],
            )

        self.assertEqual(result["succeeded"], 1)


if __name__ == "__main__":
    unittest.main()
