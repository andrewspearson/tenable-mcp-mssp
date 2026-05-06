"""FastMCP server entrypoint for the Simple MCP project."""

from __future__ import annotations

from fastmcp import FastMCP

from simple_mcp import __version__
from simple_mcp.mssp_accounts import list_child_accounts


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


def main() -> None:
    """Run the MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
