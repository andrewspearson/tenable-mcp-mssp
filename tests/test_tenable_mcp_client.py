"""Tests for Tenable hosted MCP client helpers."""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from tenable_mcp_mssp.tenable_mcp_client import (
    API_KEYS_HEADER_NAME,
    TENABLE_MCP_URL,
    TenableMcpClientError,
    build_api_keys_header,
    call_tenable_mcp_tool,
    create_tenable_mcp_client,
    list_tenable_mcp_tools,
)


@dataclass(frozen=True, slots=True)
class FakeTool:
    """Minimal fake MCP tool object."""

    name: str
    description: str
    inputSchema: dict[str, object]


class FakeAsyncClient:
    """Minimal fake async MCP client."""

    def __init__(
        self,
        tools: list[FakeTool] | None = None,
        tool_result: object | None = None,
    ) -> None:
        self.tools = tools or []
        self.tool_result = tool_result
        self.called_tool_name: str | None = None
        self.called_arguments: dict[str, object] | None = None

    async def __aenter__(self) -> "FakeAsyncClient":
        """Enter the async context manager."""

        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the async context manager."""

    async def list_tools(self) -> list[FakeTool]:
        """Return fake tools."""

        return self.tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, object],
    ) -> object:
        """Capture a fake tool call and return the fake result."""

        self.called_tool_name = name
        self.called_arguments = arguments
        return self.tool_result


class TenableMcpClientTests(unittest.IsolatedAsyncioTestCase):
    """Tests for Tenable hosted MCP client helpers."""

    def test_build_api_keys_header(self) -> None:
        """The X-ApiKeys header value should match Tenable's expected format."""

        self.assertEqual(
            build_api_keys_header(" access ", " secret "),
            "accessKey=access;secretKey=secret",
        )

    def test_blank_access_key_raises_error(self) -> None:
        """Blank access keys should fail before client creation."""

        with self.assertRaisesRegex(TenableMcpClientError, "access_key"):
            build_api_keys_header(" ", "secret")

    def test_blank_secret_key_raises_error(self) -> None:
        """Blank secret keys should fail before client creation."""

        with self.assertRaisesRegex(TenableMcpClientError, "secret_key"):
            build_api_keys_header("access", " ")

    def test_create_tenable_mcp_client_uses_url_and_header(self) -> None:
        """Client creation should configure the hosted MCP URL and header."""

        client = create_tenable_mcp_client("access", "secret")

        self.assertEqual(client.transport.url, TENABLE_MCP_URL)
        self.assertEqual(
            client.transport.headers,
            {API_KEYS_HEADER_NAME: "accessKey=access;secretKey=secret"},
        )

    async def test_list_tenable_mcp_tools_normalizes_tools(self) -> None:
        """Tool listing should return JSON-friendly tool dictionaries."""

        fake_client = FakeAsyncClient(
            tools=[
                FakeTool(
                    name="scan_list",
                    description="List scans.",
                    inputSchema={"type": "object"},
                )
            ]
        )

        tools = await list_tenable_mcp_tools(
            "access",
            "secret",
            client_factory=lambda access_key, secret_key: fake_client,
        )

        self.assertEqual(
            tools,
            [
                {
                    "name": "scan_list",
                    "description": "List scans.",
                    "input_schema": {"type": "object"},
                }
            ],
        )

    async def test_blank_tool_name_raises_error(self) -> None:
        """Blank tool names should fail before the MCP call."""

        with self.assertRaisesRegex(TenableMcpClientError, "tool_name"):
            await call_tenable_mcp_tool("access", "secret", " ")

    async def test_non_dict_arguments_raise_error(self) -> None:
        """Non-dictionary tool arguments should fail before the MCP call."""

        with self.assertRaisesRegex(TenableMcpClientError, "arguments"):
            await call_tenable_mcp_tool(
                "access",
                "secret",
                "scan_list",
                arguments=["not-a-dict"],
            )

    async def test_call_tenable_mcp_tool_uses_fake_client(self) -> None:
        """Tool calls should pass name and arguments to the MCP client."""

        result = {"ok": True}
        fake_client = FakeAsyncClient(tool_result=result)

        call_result = await call_tenable_mcp_tool(
            "access",
            "secret",
            "scan_list",
            arguments={"limit": 5},
            client_factory=lambda access_key, secret_key: fake_client,
        )

        self.assertEqual(call_result, result)
        self.assertEqual(fake_client.called_tool_name, "scan_list")
        self.assertEqual(fake_client.called_arguments, {"limit": 5})


if __name__ == "__main__":
    unittest.main()
