"""Entry point for the Zammad MCP server."""

from .config import TransportConfig, TransportType
from .logging_config import configure_logging


def main() -> None:
    """Run the MCP server with configured transport.

    Transport is configured via environment variables:
    - MCP_TRANSPORT: 'stdio' (default) or 'http'
    - MCP_HOST: Host for HTTP transport (default: 127.0.0.1)
    - MCP_PORT: Port for HTTP transport (required if transport=http)
    """
    # Configure logging before importing server code to prevent stdout leakage.
    configure_logging()

    # Load and validate transport configuration before server module initialization.
    config = TransportConfig.from_env()
    config.validate()

    from .server import mcp  # noqa: PLC0415

    # FastMCP handles its own async loop.
    # Host and port are already configured during server initialization.
    if config.transport == TransportType.HTTP:
        mcp.run(transport="streamable-http")  # type: ignore[func-returns-value]
    else:
        mcp.run()  # type: ignore[func-returns-value]


if __name__ == "__main__":
    main()
