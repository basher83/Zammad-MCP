"""Entry point for the Zammad MCP server."""

from pathlib import Path

from dotenv import load_dotenv

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

    # Load the working-directory .env before transport and OAuth settings.
    # python-dotenv's default search starts from this file, not the process cwd.
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env)

    # Load and validate transport configuration before server module initialization.
    config = TransportConfig.from_env()
    config.validate()

    from .server import mcp  # noqa: PLC0415

    if config.transport == TransportType.HTTP:
        mcp.run(transport="http", host=config.host, port=config.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
