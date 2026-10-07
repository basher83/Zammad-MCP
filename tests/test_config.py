"""Tests for server configuration."""

from unittest.mock import patch

import pytest

from mcp_zammad.config import (
    ZAMMAD_OAUTH_SCOPES,
    AuthConfig,
    PassthroughTokenVerifier,
    TransportConfig,
    TransportType,
)


def test_transport_config_defaults() -> None:
    """Test default transport configuration."""
    config = TransportConfig()
    assert config.transport == TransportType.STDIO
    assert config.host is None
    assert config.port is None


def test_transport_config_http_from_env(monkeypatch) -> None:
    """Test HTTP transport configuration from environment."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "8080")

    config = TransportConfig.from_env()
    assert config.transport == TransportType.HTTP
    assert config.host == "0.0.0.0"
    assert config.port == 8080


def test_transport_config_transport_case_insensitive(monkeypatch) -> None:
    """Test MCP_TRANSPORT accepts any case."""
    monkeypatch.setenv("MCP_TRANSPORT", "HTTP")
    monkeypatch.setenv("MCP_PORT", "8080")

    config = TransportConfig.from_env()
    assert config.transport == TransportType.HTTP


def test_transport_config_stdio_from_env(monkeypatch) -> None:
    """Test stdio transport configuration from environment."""
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")

    config = TransportConfig.from_env()
    assert config.transport == TransportType.STDIO
    assert config.host is None
    assert config.port is None


def test_transport_config_invalid_transport(monkeypatch) -> None:
    """Test invalid transport type raises error."""
    monkeypatch.setenv("MCP_TRANSPORT", "invalid")

    with pytest.raises(ValueError, match="Invalid transport type"):
        TransportConfig.from_env()


def test_transport_config_http_defaults_port(monkeypatch) -> None:
    """Test HTTP transport defaults port to 8000."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.delenv("MCP_PORT", raising=False)

    config = TransportConfig.from_env()
    config.validate()
    assert config.port == 8000


def test_transport_config_http_defaults_host() -> None:
    """Test HTTP transport defaults to localhost."""
    config = TransportConfig(transport=TransportType.HTTP, port=8000)
    config.validate()
    assert config.host == "127.0.0.1"


def test_transport_config_port_non_numeric(monkeypatch) -> None:
    """Test non-numeric port string raises error."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_PORT", "not_a_number")

    with pytest.raises(ValueError, match="MCP_PORT must be a valid integer"):
        TransportConfig.from_env()


@pytest.mark.parametrize("port", [0, 65536, -1])
def test_transport_config_invalid_port(port) -> None:
    """Test invalid port values raise error."""
    config = TransportConfig(transport=TransportType.HTTP, port=port)
    with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
        config.validate()


@pytest.mark.parametrize(
    ("certfile", "keyfile"),
    [("cert.pem", None), (None, "key.pem")],
)
def test_transport_config_ssl_files_must_be_paired(tmp_path, certfile, keyfile) -> None:
    """Setting only one of the SSL files must fail instead of silently serving plain HTTP."""
    config = TransportConfig(
        transport=TransportType.HTTP,
        ssl_certfile=str(tmp_path / certfile) if certfile else None,
        ssl_keyfile=str(tmp_path / keyfile) if keyfile else None,
    )
    with pytest.raises(ValueError, match="must be set together"):
        config.validate()


def test_transport_config_ssl_file_missing(tmp_path) -> None:
    """A configured SSL file that does not exist fails at validation, not when uvicorn starts."""
    cert = tmp_path / "cert.pem"
    cert.write_text("cert")
    config = TransportConfig(
        transport=TransportType.HTTP,
        ssl_certfile=str(cert),
        ssl_keyfile=str(tmp_path / "missing.pem"),
    )
    with pytest.raises(ValueError, match="MCP_SSL_KEYFILE must point to a readable file"):
        config.validate()


def test_transport_config_ssl_files_valid(tmp_path) -> None:
    """Readable certificate and key files pass validation and reach the uvicorn config."""
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert.write_text("cert")
    key.write_text("key")
    config = TransportConfig(transport=TransportType.HTTP, ssl_certfile=str(cert), ssl_keyfile=str(key))
    config.validate()
    assert config.get_uvicorn_config() == {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}


# --- AuthConfig tests ---


def test_auth_config_defaults() -> None:
    """Test default auth configuration (disabled)."""
    config = AuthConfig()
    assert not config.enabled
    assert config.client_id is None
    assert config.zammad_base_url is None


def test_auth_config_disabled_when_no_env(monkeypatch) -> None:
    """Test auth is disabled when no auth env vars are set."""
    for var in ("MCP_AUTH_CLIENT_ID", "MCP_AUTH_CLIENT_SECRET", "MCP_AUTH_BASE_URL", "ZAMMAD_URL"):
        monkeypatch.delenv(var, raising=False)
    config = AuthConfig.from_env()
    assert not config.enabled
    assert config.create_auth_provider() is None


def test_auth_config_from_env(monkeypatch) -> None:
    """Test auth configuration from environment variables."""
    monkeypatch.setenv("ZAMMAD_URL", "https://your-instance.zammad.com/api/v1")
    monkeypatch.setenv("MCP_AUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MCP_AUTH_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("MCP_AUTH_BASE_URL", "http://localhost:8000")

    config = AuthConfig.from_env()
    assert config.client_id == "test-client-id"
    assert config.client_secret == "test-secret"
    assert config.zammad_base_url == "https://your-instance.zammad.com"
    assert config.base_url == "http://localhost:8000"
    assert config.enabled


def test_auth_config_strips_api_suffix_from_zammad_url(monkeypatch) -> None:
    """Test ZAMMAD_URL /api/v1 suffix is stripped for OAuth base URL."""
    monkeypatch.setenv("ZAMMAD_URL", "https://tickets.example.com/api/v1")
    monkeypatch.setenv("MCP_AUTH_CLIENT_ID", "test-id")

    config = AuthConfig.from_env()
    assert config.zammad_base_url == "https://tickets.example.com"


def test_auth_config_zammad_url_without_api_suffix(monkeypatch) -> None:
    """Test ZAMMAD_URL without /api/v1 suffix is used as-is."""
    monkeypatch.setenv("ZAMMAD_URL", "https://tickets.example.com")
    monkeypatch.setenv("MCP_AUTH_CLIENT_ID", "test-id")

    config = AuthConfig.from_env()
    assert config.zammad_base_url == "https://tickets.example.com"


def test_auth_config_enabled_partial_config() -> None:
    """Test enabled is True when at least one auth field is set."""
    config = AuthConfig(client_id="some-id")
    assert config.enabled


def test_auth_config_validate_missing_client_id() -> None:
    """Test validation fails when client_id is missing."""
    config = AuthConfig(
        client_secret="secret",
        zammad_base_url="https://z.example.com",
        base_url="http://localhost:8000",
    )
    with pytest.raises(ValueError, match="MCP_AUTH_CLIENT_ID"):
        config.validate()


def test_auth_config_validate_missing_client_secret() -> None:
    """Test validation fails when client_secret is missing."""
    config = AuthConfig(
        client_id="id",
        zammad_base_url="https://z.example.com",
        base_url="http://localhost:8000",
    )
    with pytest.raises(ValueError, match="MCP_AUTH_CLIENT_SECRET"):
        config.validate()


def test_auth_config_validate_missing_zammad_url() -> None:
    """Test validation fails when ZAMMAD_URL is missing."""
    config = AuthConfig(
        client_id="id",
        client_secret="secret",
        base_url="http://localhost:8000",
    )
    with pytest.raises(ValueError, match="ZAMMAD_URL"):
        config.validate()


def test_auth_config_validate_missing_base_url() -> None:
    """Test validation fails when base_url is missing."""
    config = AuthConfig(
        client_id="id",
        client_secret="secret",
        zammad_base_url="https://z.example.com",
    )
    with pytest.raises(ValueError, match="MCP_AUTH_BASE_URL"):
        config.validate()


def test_auth_config_validate_multiple_missing() -> None:
    """Test validation reports all missing fields."""
    config = AuthConfig(client_id="id")
    with pytest.raises(ValueError, match=r"MCP_AUTH_CLIENT_SECRET.*ZAMMAD_URL.*MCP_AUTH_BASE_URL"):
        config.validate()


def test_auth_config_validate_disabled_is_noop() -> None:
    """Test validation passes when auth is disabled."""
    config = AuthConfig()
    config.validate()  # should not raise


def test_auth_config_create_provider() -> None:
    """Test OAuthProxy creation with valid config."""
    config = AuthConfig(
        client_id="test-id",
        client_secret="test-secret",
        zammad_base_url="https://your-instance.zammad.com",
        base_url="http://localhost:8000",
    )

    with patch("mcp_zammad.config.OAuthProxy") as mock_proxy_cls:
        mock_proxy_instance = mock_proxy_cls.return_value
        result = config.create_auth_provider()

        assert result is mock_proxy_instance
        mock_proxy_cls.assert_called_once()
        call_kwargs = mock_proxy_cls.call_args.kwargs
        assert call_kwargs["upstream_authorization_endpoint"] == "https://your-instance.zammad.com/oauth/authorize"
        assert call_kwargs["upstream_token_endpoint"] == "https://your-instance.zammad.com/oauth/token"
        assert call_kwargs["upstream_client_id"] == "test-id"
        assert call_kwargs["upstream_client_secret"] == "test-secret"
        assert call_kwargs["base_url"] == "http://localhost:8000"
        assert call_kwargs["valid_scopes"] == ZAMMAD_OAUTH_SCOPES
        assert isinstance(call_kwargs["token_verifier"], PassthroughTokenVerifier)


def test_auth_config_create_provider_disabled() -> None:
    """Test create_auth_provider returns None when disabled."""
    config = AuthConfig()
    assert config.create_auth_provider() is None


# --- PassthroughTokenVerifier tests ---


def test_passthrough_verifier_declares_full_scope() -> None:
    """Test PassthroughTokenVerifier declares 'full' as required scope.

    This is critical for OAuthProxy: required_scopes propagates to
    _default_scope_str, which is assigned to dynamically registered
    clients during DCR.  Without it, clients get empty scopes and
    authorization requests for scope 'full' are rejected.
    """
    verifier = PassthroughTokenVerifier()
    assert verifier.required_scopes == ZAMMAD_OAUTH_SCOPES


@pytest.mark.asyncio
async def test_passthrough_verifier_returns_access_token() -> None:
    """Test PassthroughTokenVerifier wraps token in AccessToken."""
    verifier = PassthroughTokenVerifier()
    result = await verifier.verify_token("test-upstream-token")
    assert result is not None
    assert result.token == "test-upstream-token"
    assert result.client_id == "upstream"
    assert result.scopes == ZAMMAD_OAUTH_SCOPES
    assert result.expires_at is not None
