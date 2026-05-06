"""FastMCP server entrypoint for the Simple MCP project."""

from __future__ import annotations

from fastmcp import FastMCP

from simple_mcp import __version__
from simple_mcp.mssp_accounts import list_child_accounts_as_dicts


def list_mssp_child_accounts() -> list[dict[str, str]]:
    """List Tenable MSSP child account names and UUIDs."""

    return list_child_accounts_as_dicts()


def create_server() -> FastMCP:
    """Create and configure the FastMCP server."""

    server = FastMCP(
        name="Tenable MSSP MCP",
        instructions="List Tenable MSSP child accounts.",
        version=__version__,
    )
    server.tool(
        name="list_mssp_child_accounts",
        description="List Tenable MSSP child account names and UUIDs.",
    )(list_mssp_child_accounts)

    return server


mcp = create_server()


def main() -> None:
    """Run the MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
