"""FastMCP server entrypoint for the Tenable MCP MSSP project."""

from __future__ import annotations

import logging

from fastmcp import Context, FastMCP

from tenable_mcp_mssp import __version__
from tenable_mcp_mssp.child_container_scope import (
    get_child_container_scope as get_scope_report,
    load_child_container_scope,
)
from tenable_mcp_mssp.logging_config import configure_logging
from tenable_mcp_mssp.mssp_accounts import list_child_accounts
from tenable_mcp_mssp.multi_child_tenable_mcp import (
    run_tenable_mcp_recipe_across_child_containers as run_recipe_across_children,
)
from tenable_mcp_mssp.single_child_tenable_mcp import (
    list_available_tenable_mcp_tools as list_tools_for_child,
    run_tenable_mcp_recipe_for_child as run_recipe_for_child,
    run_tenable_mcp_tool_for_child as run_tool_for_child,
)


logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="Tenable MSSP MCP",
    instructions=(
        "Use this MCP server to orchestrate Tenable MSSP child-container work. "
        "List child accounts first, discover official Tenable MCP tools on one "
        "child, experiment with one tool on one child, validate known recipes "
        "on one child, then use multi-child fan-out only after the recipe is "
        "known to work. Child API keys are generated internally, kept in "
        "memory only, and never returned by public tools. Child-container "
        "action tools honor the configured positive allowlist when one is set."
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
    name="get_child_container_scope",
    description=(
        "Show the configured child container allowlist scope for action tools."
    ),
)
def get_child_container_scope() -> dict[str, object]:
    """Return the configured child container action scope."""

    return get_scope_report()


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
    ctx: Context | None = None,
) -> dict[str, object]:
    """Run a recipe of official Tenable MCP tools across child containers."""

    async def report_progress(done: int, total: int, message: str) -> None:
        if ctx is None:
            return

        await ctx.info(message)
        await ctx.report_progress(done, total, message)

    return await run_recipe_across_children(
        child_container_uuids,
        recipe,
        required_license,
        progress_reporter=report_progress,
    )


def main() -> None:
    """Run the MCP server."""

    configure_logging()
    load_child_container_scope()
    logger.info("Starting Tenable MCP MSSP server version %s.", __version__)
    mcp.run()


if __name__ == "__main__":
    main()
