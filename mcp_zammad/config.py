"""Configuration for MCP server transport."""

import os
from dataclasses import dataclass
from enum import Enum


class TransportType(str, Enum):
    """Supported transport types."""

    STDIO = "stdio"
    HTTP = "http"


@dataclass
class TransportConfig:
    """Configuration for MCP transport layer.

    Attributes:
        transport: Transport type (stdio or http)
        host: Host address for HTTP transport (default: 127.0.0.1)
        port: Port number for HTTP transport (required for HTTP)
    """

    transport: TransportType = TransportType.STDIO
    host: str | None = None
    port: int | None = None

    @classmethod
    def from_env(cls) -> "TransportConfig":
        """Create configuration from environment variables.

        Environment Variables:
            MCP_TRANSPORT: Transport type (stdio or http, default: stdio)
            MCP_HOST: Host address for HTTP (default: 127.0.0.1)
            MCP_PORT: Port number for HTTP (required if transport=http)

        Returns:
            TransportConfig instance

        Raises:
            ValueError: If transport type is invalid
        """
        transport_str = os.getenv("MCP_TRANSPORT", "stdio").lower()

        try:
            transport = TransportType(transport_str)
        except ValueError:
            raise ValueError(
                f"Invalid transport type: {transport_str}. Must be one of: {', '.join(t.value for t in TransportType)}"
            ) from None

        host = os.getenv("MCP_HOST")
        port_str = os.getenv("MCP_PORT")
        port = int(port_str) if port_str else None

        return cls(transport=transport, host=host, port=port)

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        if self.transport == TransportType.HTTP:
            if self.port is None:
                raise ValueError("HTTP transport requires MCP_PORT environment variable")

            # Default host to localhost for HTTP if not specified
            if self.host is None:
                self.host = "127.0.0.1"
