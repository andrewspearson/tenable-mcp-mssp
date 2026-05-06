"""Single-child orchestration helpers for Tenable's hosted MCP server."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from simple_mcp.child_credentials import (
    ChildCredential,
    get_or_generate_child_credentials,
)
from simple_mcp.tenable_mcp_client import list_tenable_mcp_tools


async def list_available_tenable_mcp_tools(
    child_container_uuid: str,
    credential_provider: Callable[[str], ChildCredential] = (
        get_or_generate_child_credentials
    ),
    tool_lister: Callable[[str, str], Any] = list_tenable_mcp_tools,
) -> list[dict[str, Any]]:
    """List official Tenable MCP tools available to a child container."""

    credential = credential_provider(child_container_uuid)
    return await tool_lister(
        credential.access_key,
        credential.secret_key,
    )
