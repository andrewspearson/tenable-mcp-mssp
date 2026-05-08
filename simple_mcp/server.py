"""FastMCP server entrypoint for the Simple MCP project."""

from __future__ import annotations

from fastmcp import FastMCP

from simple_mcp import __version__
from simple_mcp.mssp_accounts import list_child_accounts
from simple_mcp.multi_child_tenable_mcp import (
    run_tenable_mcp_recipe_across_child_containers as run_recipe_across_children,
)
from simple_mcp.single_child_tenable_mcp import (
    list_available_tenable_mcp_tools as list_tools_for_child,
    run_tenable_mcp_recipe_for_child as run_recipe_for_child,
    run_tenable_mcp_tool_for_child as run_tool_for_child,
)


mcp = FastMCP(
    name="Tenable MSSP MCP",
    instructions=(
        "Use this MCP server to orchestrate Tenable MSSP child-container work. "
        "List child accounts first, discover official Tenable MCP tools on one "
        "child, experiment with one tool on one child, validate known recipes "
        "on one child, then use multi-child fan-out only after the recipe is "
        "known to work. Child API keys are generated internally, kept in "
        "memory only, and never returned by public tools."
    ),
    version=__version__,
)


@mcp.tool(
    name="list_mssp_child_accounts",
    description=(
        "List raw Tenable MSSP child account objects, including license data."
    ),
)
def list_mssp_child_accounts() -> list[dict[str, object]]:
    """List Tenable MSSP child accounts."""

    return list_child_accounts()


@mcp.tool(
    name="list_available_tenable_mcp_tools",
    description=(
        "Discover official Tenable MCP tools available for one child container."
    ),
)
async def list_available_tenable_mcp_tools(
    child_container_uuid: str,
) -> list[dict[str, object]]:
    """List official Tenable MCP tools for a child container."""

    return await list_tools_for_child(child_container_uuid)


@mcp.tool(
    name="run_tenable_mcp_tool_for_child",
    description=(
        "Explore by running one official Tenable MCP tool on one child container."
    ),
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
    description=(
        "Validate a known sequence of official Tenable MCP tools on one child."
    ),
)
async def run_tenable_mcp_recipe_for_child(
    child_container_uuid: str,
    recipe: list[dict[str, object]],
) -> dict[str, object]:
    """Run a recipe of official Tenable MCP tools for a child container."""

    return await run_recipe_for_child(child_container_uuid, recipe)


@mcp.tool(
    name="run_tenable_mcp_recipe_across_child_containers",
    description=(
        "Run a known working recipe across child containers with controlled fan-out."
    ),
)
async def run_tenable_mcp_recipe_across_child_containers(
    child_container_uuids: list[str],
    recipe: list[dict[str, object]],
    required_license: str | None = None,
) -> dict[str, object]:
    """Run a recipe of official Tenable MCP tools across child containers."""

    return await run_recipe_across_children(
        child_container_uuids,
        recipe,
        required_license,
    )


def main() -> None:
    """Run the MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
