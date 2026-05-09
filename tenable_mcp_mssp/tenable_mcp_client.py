"""Client helpers for Tenable's hosted MCP server."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastmcp import Client
from fastmcp.client import StreamableHttpTransport


TENABLE_MCP_URL = "https://cloud.tenable.com/mcp/"
API_KEYS_HEADER_NAME = "X-ApiKeys"
logger = logging.getLogger(__name__)


class TenableMcpClientError(RuntimeError):
    """Raised when Tenable MCP client setup or calls fail."""


def build_api_keys_header(access_key: str, secret_key: str) -> str:
    """Build a Tenable X-ApiKeys header value."""

    clean_access_key = _require_non_empty_string(access_key, "access_key")
    clean_secret_key = _require_non_empty_string(secret_key, "secret_key")
    return f"accessKey={clean_access_key};secretKey={clean_secret_key}"


def create_tenable_mcp_client(access_key: str, secret_key: str) -> Client:
    """Create a FastMCP client for Tenable's hosted MCP server."""

    transport = StreamableHttpTransport(
        TENABLE_MCP_URL,
        headers={
            API_KEYS_HEADER_NAME: build_api_keys_header(access_key, secret_key),
        },
    )
    return Client(transport)


async def list_tenable_mcp_tools(
    access_key: str,
    secret_key: str,
    client_factory: Callable[[str, str], Any] = create_tenable_mcp_client,
) -> list[dict[str, Any]]:
    """List tools available from Tenable's hosted MCP server."""

    build_api_keys_header(access_key, secret_key)

    try:
        async with client_factory(access_key, secret_key) as client:
            tools = await client.list_tools()
    except Exception as exc:
        logger.warning("Failed to list Tenable Hexa AI MCP tools.")
        raise TenableMcpClientError("Failed to list Tenable MCP tools.") from exc

    return [_normalize_tool(tool) for tool in tools]


async def call_tenable_mcp_tool(
    access_key: str,
    secret_key: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    client_factory: Callable[[str, str], Any] = create_tenable_mcp_client,
) -> object:
    """Call a tool on Tenable's hosted MCP server."""

    build_api_keys_header(access_key, secret_key)
    clean_tool_name = _require_non_empty_string(tool_name, "tool_name")

    if arguments is None:
        tool_arguments: dict[str, Any] = {}
    elif isinstance(arguments, dict):
        tool_arguments = arguments
    else:
        raise TenableMcpClientError("arguments must be a dictionary.")

    try:
        async with client_factory(access_key, secret_key) as client:
            return await client.call_tool(clean_tool_name, tool_arguments)
    except Exception as exc:
        logger.warning("Failed to call Tenable Hexa AI MCP tool %s.", clean_tool_name)
        raise TenableMcpClientError(
            f"Failed to call Tenable MCP tool: {clean_tool_name}."
        ) from exc


def _normalize_tool(tool: Any) -> dict[str, Any]:
    """Return a JSON-friendly representation of an MCP tool."""

    return {
        "name": getattr(tool, "name", None),
        "description": getattr(tool, "description", None),
        "input_schema": getattr(tool, "inputSchema", None),
    }


def _require_non_empty_string(value: str, field_name: str) -> str:
    """Validate and normalize a required string value."""

    if not isinstance(value, str) or not value.strip():
        raise TenableMcpClientError(f"{field_name} must be a non-empty string.")

    return value.strip()
