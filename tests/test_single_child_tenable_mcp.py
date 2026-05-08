"""Tests for single-child Tenable MCP orchestration."""

from __future__ import annotations

import unittest

from simple_mcp.child_credentials import ChildCredential
from simple_mcp.single_child_tenable_mcp import (
    list_available_tenable_mcp_tools,
    run_tenable_mcp_tool_for_child,
)


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

    async def test_run_tenable_mcp_tool_for_child_forwards_call_inputs(
        self,
    ) -> None:
        """Tool runner should receive child keys, tool name, and arguments."""

        credential = ChildCredential(
            child_container_uuid="child-uuid",
            access_key="stored-access-key",
            secret_key="stored-secret-key",
        )
        arguments = {"plugin_id": "12345"}
        tool_result = {"status": "ok", "items": [{"id": 1}]}
        calls: list[
            tuple[str, str, str, dict[str, object] | None]
        ] = []

        async def fake_tool_runner(
            access_key: str,
            secret_key: str,
            tool_name: str,
            tool_arguments: dict[str, object] | None = None,
        ) -> object:
            calls.append(
                (access_key, secret_key, tool_name, tool_arguments)
            )
            return tool_result

        result = await run_tenable_mcp_tool_for_child(
            "child-uuid",
            "vulnerability_findings",
            arguments,
            credential_provider=lambda child_uuid: credential,
            tool_runner=fake_tool_runner,
        )

        self.assertIs(result, tool_result)
        self.assertEqual(
            calls,
            [
                (
                    "stored-access-key",
                    "stored-secret-key",
                    "vulnerability_findings",
                    arguments,
                )
            ],
        )

    async def test_run_tenable_mcp_tool_for_child_handles_none_arguments(
        self,
    ) -> None:
        """None arguments should be forwarded to the lower-level helper."""

        credential = ChildCredential(
            child_container_uuid="child-uuid",
            access_key="stored-access-key",
            secret_key="stored-secret-key",
        )
        calls: list[
            tuple[str, str, str, dict[str, object] | None]
        ] = []

        async def fake_tool_runner(
            access_key: str,
            secret_key: str,
            tool_name: str,
            tool_arguments: dict[str, object] | None = None,
        ) -> object:
            calls.append(
                (access_key, secret_key, tool_name, tool_arguments)
            )
            return ["official-result"]

        result = await run_tenable_mcp_tool_for_child(
            "child-uuid",
            "asset_list",
            credential_provider=lambda child_uuid: credential,
            tool_runner=fake_tool_runner,
        )

        self.assertEqual(result, ["official-result"])
        self.assertEqual(
            calls,
            [
                (
                    "stored-access-key",
                    "stored-secret-key",
                    "asset_list",
                    None,
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
