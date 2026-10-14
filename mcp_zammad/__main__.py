"""Entry point for the Zammad MCP server."""

import logging
import sys

from .config import TransportConfig, TransportType
from .logging_config import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the MCP server with configured transport.

    Transport is configured via environment variables:
    - MCP_TRANSPORT: 'stdio' (default) or 'http'
    - MCP_HOST: Host for HTTP transport (default: 127.0.0.1)
    - MCP_PORT: Port for HTTP transport (default: 8000)
    """
    configure_logging()
    config = TransportConfig.from_env()
    config.validate()

    from .server import mcp  # noqa: PLC0415

    try:
        if config.transport == TransportType.HTTP:
            mcp.run(
                transport="http",
                host=config.host,
                port=config.port,
                uvicorn_config=config.get_uvicorn_config(),
            )
        else:
            mcp.run()
    except KeyboardInterrupt:
        pass
    except ValueError as e:
        logger.error("Configuration error: %s", e)  # noqa: TRY400
        sys.exit(1)
    except RuntimeError as e:
        logger.error("Runtime error: %s", e)  # noqa: TRY400
        sys.exit(1)
    except Exception:
        logger.exception("Internal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
