"""Tests proving ZammadClient installs the resilient session boundary."""

import os
from unittest.mock import MagicMock, patch

import pytest
from zammad_py.exceptions import ConfigException

from mcp_zammad.client import ZammadClient
from mcp_zammad.resilience import ResilientSession

_ENV = {"ZAMMAD_URL": "https://test.zammad.com/api/v1", "ZAMMAD_HTTP_TOKEN": "test-token"}


@patch("mcp_zammad.client.ZammadAPI")
def test_client_wraps_api_session(mock_api: MagicMock) -> None:
    original_session = mock_api.return_value.session

    with patch.dict(os.environ, _ENV, clear=True):
        client = ZammadClient()

    assert isinstance(client.api.session, ResilientSession)
    assert client.api.session.wrapped is original_session


@patch("mcp_zammad.client.ZammadAPI")
def test_client_reads_resilience_config_from_env(mock_api: MagicMock) -> None:
    with patch.dict(os.environ, {**_ENV, "ZAMMAD_RATE_LIMIT_ENABLED": "true", "ZAMMAD_MAX_RETRIES": "7"}, clear=True):
        client = ZammadClient()

    assert client.resilience.rate_limit_enabled is True
    assert client.resilience.max_retries == 7


@patch("mcp_zammad.client.ZammadAPI")
def test_client_rejects_invalid_resilience_config(mock_api: MagicMock) -> None:
    with (
        patch.dict(os.environ, {**_ENV, "ZAMMAD_MAX_RETRIES": "lots"}, clear=True),
        pytest.raises(ConfigException, match="ZAMMAD_MAX_RETRIES"),
    ):
        ZammadClient()


@patch("mcp_zammad.client.ZammadAPI")
def test_insecure_mode_still_disables_tls_on_wrapped_session(mock_api: MagicMock) -> None:
    original_session = mock_api.return_value.session

    with patch.dict(os.environ, {**_ENV, "ZAMMAD_INSECURE": "true"}, clear=True):
        client = ZammadClient()

    assert original_session.verify is False
    assert client.api.session.verify is False
