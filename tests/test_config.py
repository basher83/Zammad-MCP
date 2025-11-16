"""Tests for server configuration."""

import pytest

from mcp_zammad.config import TransportConfig, TransportType


def test_transport_config_defaults():
    """Test default transport configuration."""
    config = TransportConfig()
    assert config.transport == TransportType.STDIO
    assert config.host is None
    assert config.port is None


def test_transport_config_http_from_env(monkeypatch):
    """Test HTTP transport configuration from environment."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "8080")

    config = TransportConfig.from_env()
    assert config.transport == TransportType.HTTP
    assert config.host == "0.0.0.0"
    assert config.port == 8080


def test_transport_config_stdio_from_env(monkeypatch):
    """Test stdio transport configuration from environment."""
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")

    config = TransportConfig.from_env()
    assert config.transport == TransportType.STDIO
    assert config.host is None
    assert config.port is None


def test_transport_config_invalid_transport(monkeypatch):
    """Test invalid transport type raises error."""
    monkeypatch.setenv("MCP_TRANSPORT", "invalid")

    with pytest.raises(ValueError, match="Invalid transport type"):
        TransportConfig.from_env()


def test_transport_config_http_requires_port(monkeypatch):
    """Test HTTP transport requires port."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.delenv("MCP_PORT", raising=False)

    config = TransportConfig.from_env()
    with pytest.raises(ValueError, match="HTTP transport requires MCP_PORT"):
        config.validate()


def test_transport_config_http_defaults_host():
    """Test HTTP transport defaults to localhost."""
    config = TransportConfig(transport=TransportType.HTTP, port=8000)
    config.validate()
    assert config.host == "127.0.0.1"


def test_transport_config_port_non_numeric(monkeypatch):
    """Test non-numeric port string raises error."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_PORT", "not_a_number")

    with pytest.raises(ValueError, match="MCP_PORT must be a valid integer"):
        TransportConfig.from_env()


def test_transport_config_port_below_range():
    """Test port below valid range raises error."""
    config = TransportConfig(transport=TransportType.HTTP, port=0)
    with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
        config.validate()


def test_transport_config_port_above_range():
    """Test port above valid range raises error."""
    config = TransportConfig(transport=TransportType.HTTP, port=65536)
    with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
        config.validate()


def test_transport_config_port_negative():
    """Test negative port raises error."""
    config = TransportConfig(transport=TransportType.HTTP, port=-1)
    with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
        config.validate()
