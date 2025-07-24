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
