"""Configuration for MCP server transport and authentication."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from enum import Enum

from fastmcp.server.auth import AccessToken, OAuthProxy, TokenVerifier

logger = logging.getLogger(__name__)

# Zammad's Doorkeeper only supports the "full" scope.
ZAMMAD_OAUTH_SCOPES: list[str] = ["full"]

# Port validation constants
MIN_PORT = 1
MAX_PORT = 65535


class PassthroughTokenVerifier(TokenVerifier):
    """Token verifier that trusts upstream tokens obtained via OAuthProxy.

    OAuthProxy acquires upstream tokens through a legitimate OAuth authorization
    code exchange.  Re-verifying the token on every request is unnecessary when
    the upstream provider is trusted and token expiry is already tracked by
    OAuthProxy.  This verifier simply wraps the raw token string in an
    ``AccessToken`` so that downstream code (e.g., ``get_access_token().token``)
    can forward it to the upstream API.
    """

    def __init__(self) -> None:
        # Declaring required_scopes ensures OAuthProxy advertises them AND
        # assigns them to dynamically registered clients (DCR).  Without this,
        # clients get an empty scope during registration and their authorization
        # requests are rejected with "Client was not registered with scope …".
        super().__init__(required_scopes=ZAMMAD_OAUTH_SCOPES)

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an AccessToken that carries the upstream token verbatim."""
        # expires_at is nominal; OAuthProxy manages actual token refresh.
        return AccessToken(
            token=token,
            client_id="upstream",
            scopes=ZAMMAD_OAUTH_SCOPES,
            expires_at=int(time.time()) + 3600,
        )


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
        port: Port number for HTTP transport (default: 8000)
        ssl_certfile: Path to SSL certificate file (enables HTTPS)
        ssl_keyfile: Path to SSL private key file (required with ssl_certfile)
    """

    transport: TransportType = TransportType.STDIO
    host: str | None = None
    port: int | None = None
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None

    @classmethod
    def from_env(cls) -> TransportConfig:
        """Create configuration from environment variables.

        Environment Variables:
            MCP_TRANSPORT: Transport type (stdio or http, default: stdio)
            MCP_HOST: Host address for HTTP (default: 127.0.0.1)
            MCP_PORT: Port number for HTTP (default: 8000)
            MCP_SSL_CERTFILE: Path to SSL certificate (enables HTTPS)
            MCP_SSL_KEYFILE: Path to SSL private key

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
        port = None
        if port_str:
            try:
                port = int(port_str)
            except ValueError:
                raise ValueError(f"MCP_PORT must be a valid integer, got: {port_str}") from None

        return cls(
            transport=transport,
            host=host,
            port=port,
            ssl_certfile=os.getenv("MCP_SSL_CERTFILE"),
            ssl_keyfile=os.getenv("MCP_SSL_KEYFILE"),
        )

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        if self.transport == TransportType.HTTP:
            # Default port to 8000 for HTTP if not specified
            if self.port is None:
                self.port = 8000

            # Validate port range
            if not (MIN_PORT <= self.port <= MAX_PORT):
                raise ValueError(f"Port must be between {MIN_PORT} and {MAX_PORT}, got: {self.port}")

            # Default host to localhost for HTTP if not specified
            if self.host is None:
                self.host = "127.0.0.1"

    def get_uvicorn_config(self) -> dict[str, object] | None:
        """Build uvicorn extras (SSL settings) for ``mcp.run()``, or None if empty."""
        config: dict[str, object] = {}
        if self.ssl_certfile:
            config["ssl_certfile"] = self.ssl_certfile
        if self.ssl_keyfile:
            config["ssl_keyfile"] = self.ssl_keyfile
        return config or None


@dataclass
class AuthConfig:
    """Configuration for OAuth authentication via Zammad's Doorkeeper provider.

    When configured, the MCP server uses FastMCP's OAuthProxy to authenticate
    users through Zammad's built-in OAuth2 authorization server (Doorkeeper).
    Zammad's login page may offer third-party sign-in options (Google, GitHub,
    etc.) depending on the Zammad instance's configuration — that is entirely
    controlled by the Zammad admin, not by this MCP server.

    The resulting Zammad bearer token is forwarded to the Zammad API so that
    each user acts under their own identity.

    The OAuth endpoints (``/oauth/authorize``, ``/oauth/token``) are derived
    from ``ZAMMAD_URL`` automatically — Zammad's Doorkeeper always uses these
    fixed paths.

    Attributes:
        client_id: OAuth client ID from a Zammad OAuth application.
        client_secret: OAuth client secret from the Zammad OAuth application.
        zammad_base_url: Zammad instance base URL (without ``/api/v1``).
        base_url: Public URL of this MCP server (used for OAuth callbacks).
    """

    client_id: str | None = None
    client_secret: str | None = None
    zammad_base_url: str | None = None
    base_url: str | None = None

    @classmethod
    def from_env(cls) -> AuthConfig:
        """Create configuration from environment variables.

        Environment Variables:
            MCP_AUTH_CLIENT_ID: Zammad OAuth application client ID.
            MCP_AUTH_CLIENT_SECRET: Zammad OAuth application client secret.
            MCP_AUTH_BASE_URL: Public URL of this MCP server for callbacks.
            ZAMMAD_URL: Zammad instance URL (used to derive OAuth endpoints).

        Returns:
            AuthConfig instance (all None means auth disabled).
        """
        zammad_url = os.getenv("ZAMMAD_URL", "")
        zammad_base = zammad_url.removesuffix("/api/v1").rstrip("/") or None

        return cls(
            client_id=os.getenv("MCP_AUTH_CLIENT_ID"),
            client_secret=os.getenv("MCP_AUTH_CLIENT_SECRET"),
            zammad_base_url=zammad_base,
            base_url=os.getenv("MCP_AUTH_BASE_URL"),
        )

    @property
    def enabled(self) -> bool:
        """Whether authentication is configured.

        Auth is considered enabled when at least one auth-related env var is set.
        This allows ``validate()`` to report all missing variables at once rather
        than silently doing nothing.
        """
        return any([self.client_id, self.client_secret, self.base_url])

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            ValueError: If some auth fields are set but required fields are missing.
        """
        if not self.enabled:
            return

        missing = []
        if not self.client_id:
            missing.append("MCP_AUTH_CLIENT_ID")
        if not self.client_secret:
            missing.append("MCP_AUTH_CLIENT_SECRET")
        if not self.zammad_base_url:
            missing.append("ZAMMAD_URL")
        if not self.base_url:
            missing.append("MCP_AUTH_BASE_URL")
        if missing:
            raise ValueError(f"OAuth authentication requires: {', '.join(missing)}")

    def create_auth_provider(self) -> OAuthProxy | None:
        """Create an OAuthProxy pointing at Zammad's Doorkeeper endpoints.

        Returns:
            An OAuthProxy instance, or None if auth is not configured.

        Raises:
            ValueError: If configuration is invalid.
        """
        if not self.enabled:
            return None

        self.validate()
        assert self.zammad_base_url is not None  # guaranteed by validate()
        assert self.client_id is not None
        assert self.client_secret is not None
        assert self.base_url is not None

        authorize_url = f"{self.zammad_base_url}/oauth/authorize"
        token_url = f"{self.zammad_base_url}/oauth/token"

        auth_provider = OAuthProxy(
            upstream_authorization_endpoint=authorize_url,
            upstream_token_endpoint=token_url,
            upstream_client_id=self.client_id,
            upstream_client_secret=self.client_secret,
            token_verifier=PassthroughTokenVerifier(),
            base_url=self.base_url,
            # Advertise Zammad's supported scopes so MCP clients don't
            # request OIDC scopes (email, profile, openid) that Zammad
            # would reject.
            valid_scopes=ZAMMAD_OAUTH_SCOPES,
        )
        logger.info("Configured OAuth proxy → %s", authorize_url)
        return auth_provider
