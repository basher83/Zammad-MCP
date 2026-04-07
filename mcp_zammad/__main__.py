"""Entry point for the Zammad MCP server."""

from .config import TransportConfig, TransportType
from .server import mcp


def main() -> None:
    """Run the MCP server with configured transport.

    Transport is configured via environment variables:
    - MCP_TRANSPORT: 'stdio' (default) or 'http'
    - MCP_HOST: Host for HTTP transport (default: 127.0.0.1)
    - MCP_PORT: Port for HTTP transport (required if transport=http)
    """
    # Load transport configuration from environment
    config = TransportConfig.from_env()
    config.validate()

    # FastMCP handles its own async loop
    if config.transport == TransportType.HTTP:
        mcp.run(transport="http", host=config.host or "127.0.0.1", port=config.port or 8000)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
