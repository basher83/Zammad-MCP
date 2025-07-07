"""Entry point for the Zammad MCP server."""

import asyncio

from .server import mcp


async def async_main() -> None:
    """Run the MCP server asynchronously."""
    await mcp.run()  # type: ignore[func-returns-value]


def main() -> None:
    """Run the MCP server."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
