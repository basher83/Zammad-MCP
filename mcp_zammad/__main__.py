"""Entry point for the Zammad MCP server."""

from .server import mcp


def main() -> None:
    """Run the MCP server."""
    # FastMCP handles its own async loop
    mcp.run()  # type: ignore[func-returns-value]


if __name__ == "__main__":
    main()
