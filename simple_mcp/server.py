"""FastMCP server entrypoint for the Simple MCP project."""

from __future__ import annotations

from fastmcp import FastMCP

from simple_mcp import __version__
from simple_mcp.mssp_accounts import list_child_accounts
from simple_mcp.single_child_tenable_mcp import (
    list_available_tenable_mcp_tools as list_tools_for_child,
    run_tenable_mcp_recipe_for_child as run_recipe_for_child,
    run_tenable_mcp_tool_for_child as run_tool_for_child,
)


mcp = FastMCP(
    name="Tenable MSSP MCP",
    instructions="List Tenable MSSP child accounts.",
    version=__version__,
)


@mcp.tool(
    name="list_mssp_child_accounts",
    description="List Tenable MSSP child accounts.",
)
def list_mssp_child_accounts() -> list[dict[str, object]]:
    """List Tenable MSSP child accounts."""

    return list_child_accounts()


@mcp.tool(
    name="list_available_tenable_mcp_tools",
    description="List official Tenable MCP tools for a child container.",
)
async def list_available_tenable_mcp_tools(
    child_container_uuid: str,
) -> list[dict[str, object]]:
    """List official Tenable MCP tools for a child container."""

    return await list_tools_for_child(child_container_uuid)


@mcp.tool(
    name="run_tenable_mcp_tool_for_child",
    description="Run an official Tenable MCP tool for a child container.",
)
async def run_tenable_mcp_tool_for_child(
    child_container_uuid: str,
    tool_name: str,
    arguments: dict[str, object] | None = None,
) -> object:
    """Run an official Tenable MCP tool for a child container."""

    return await run_tool_for_child(child_container_uuid, tool_name, arguments)


@mcp.tool(
    name="run_tenable_mcp_recipe_for_child",
    description="Run a recipe of official Tenable MCP tools for a child container.",
)
async def run_tenable_mcp_recipe_for_child(
    child_container_uuid: str,
    recipe: list[dict[str, object]],
) -> dict[str, object]:
    """Run a recipe of official Tenable MCP tools for a child container."""

    return await run_recipe_for_child(child_container_uuid, recipe)


def main() -> None:
    """Run the MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
