"""Tests for Zammad client configuration and error handling."""

import os
from unittest.mock import MagicMock, patch

import pytest

from mcp_zammad.client import ConfigException, ZammadClient


def test_client_requires_url() -> None:
    """Test that client raises error when URL is missing."""
    with patch.dict(os.environ, {}, clear=True), pytest.raises(ConfigException, match="Zammad URL is required"):
        ZammadClient()


def test_client_requires_authentication() -> None:
    """Test that client raises error when authentication is missing."""
    with (
        patch.dict(os.environ, {"ZAMMAD_URL": "https://test.zammad.com/api/v1"}, clear=True),
        pytest.raises(ConfigException, match="Authentication credentials required"),
    ):
        ZammadClient()


def test_client_detects_wrong_token_var() -> None:
    """Test that client provides helpful error when ZAMMAD_TOKEN is used instead of ZAMMAD_HTTP_TOKEN."""
    with (
        patch.dict(
            os.environ,
            {
                "ZAMMAD_URL": "https://test.zammad.com/api/v1",
                "ZAMMAD_TOKEN": "test-token",  # Wrong variable name
            },
            clear=True,
        ),
        pytest.raises(ConfigException) as exc_info,
    ):
        ZammadClient()

    assert "Found ZAMMAD_TOKEN but this server expects ZAMMAD_HTTP_TOKEN" in str(exc_info.value)
    assert "Please rename your environment variable" in str(exc_info.value)


@patch("mcp_zammad.client.ZammadAPI")
def test_client_accepts_http_token(mock_api: MagicMock) -> None:
    """Test that client works correctly with ZAMMAD_HTTP_TOKEN."""
    with patch.dict(
        os.environ,
        {
            "ZAMMAD_URL": "https://test.zammad.com/api/v1",
            "ZAMMAD_HTTP_TOKEN": "test-token",
        },
        clear=True,
    ):
        client = ZammadClient()
        assert client.url == "https://test.zammad.com/api/v1"
        assert client.http_token == "test-token"
        mock_api.assert_called_once()


def test_url_validation_no_protocol() -> None:
    """Test that URL validation rejects URLs without protocol."""
    with patch.dict(os.environ, {"ZAMMAD_URL": "test.zammad.com", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True):
        with pytest.raises(ConfigException, match="must include protocol"):
            ZammadClient()


def test_url_validation_invalid_protocol() -> None:
    """Test that URL validation rejects non-http/https protocols."""
    with patch.dict(os.environ, {"ZAMMAD_URL": "ftp://test.zammad.com", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True):
        with pytest.raises(ConfigException, match="must use http or https"):
            ZammadClient()


def test_url_validation_no_hostname() -> None:
    """Test that URL validation rejects URLs without hostname."""
    with patch.dict(os.environ, {"ZAMMAD_URL": "https://", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True):
        with pytest.raises(ConfigException, match="must include a valid hostname"):
            ZammadClient()


@patch("mcp_zammad.client.ZammadAPI")
def test_url_validation_localhost_warning(mock_api: MagicMock, caplog) -> None:
    """Test that localhost URLs generate a warning."""
    with patch.dict(os.environ, {"ZAMMAD_URL": "http://localhost:3000", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True):
        ZammadClient()
        assert "points to local host" in caplog.text


@patch("mcp_zammad.client.ZammadAPI")
def test_url_validation_private_network_warning(mock_api: MagicMock, caplog) -> None:
    """Test that private network URLs generate a warning."""
    with patch.dict(os.environ, {"ZAMMAD_URL": "http://192.168.1.100", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True):
        ZammadClient()
        assert "points to private network" in caplog.text
