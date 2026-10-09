"""Tests for Zammad client configuration and error handling."""

import atexit
import gc
import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from mcp_zammad.client import ConfigException, ZammadAPIError, ZammadClient

# Non-secret placeholder for tests (avoids bandit S106 on auth kwargs)
_TEST_AUTH_VALUE = "test-auth-value"


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


@patch("mcp_zammad.client.ZammadAPI")
def test_explicit_oauth2_token_suppresses_static_env_credentials(mock_api: MagicMock) -> None:
    """A per-request OAuth token must not be overridden by static credentials from the environment."""
    with patch.dict(
        os.environ,
        {
            "ZAMMAD_URL": "https://test.zammad.com/api/v1",
            "ZAMMAD_HTTP_TOKEN": "static-token",
            "ZAMMAD_USERNAME": "static-user",
            "ZAMMAD_PASSWORD": "static-password",
        },
        clear=True,
    ):
        client = ZammadClient(oauth2_token=_TEST_AUTH_VALUE)

    assert client.http_token is None
    assert client.username is None
    assert client.password is None
    mock_api.assert_called_once_with(
        url="https://test.zammad.com/api/v1",
        username=None,
        password=None,
        http_token=None,
        oauth2_token=_TEST_AUTH_VALUE,
    )


def test_per_request_clients_do_not_accumulate_atexit_handlers() -> None:
    """zammad-py's per-session atexit cleanup must not pile up when the server builds a client per request."""
    before = atexit._ncallbacks()
    for _ in range(5):
        ZammadClient(url="https://test.zammad.com/api/v1", oauth2_token=_TEST_AUTH_VALUE)
    assert atexit._ncallbacks() == before


@patch("mcp_zammad.client.ZammadAPI")
def test_client_closes_its_session_when_garbage_collected(mock_api: MagicMock) -> None:
    """The finalizer that replaces the atexit handler closes the underlying session."""
    raw_session = mock_api.return_value.session
    client = ZammadClient(url="https://test.zammad.com/api/v1", oauth2_token=_TEST_AUTH_VALUE)

    del client
    gc.collect()
    raw_session.close.assert_called_once()


@pytest.mark.parametrize(
    ("ok", "status_code", "expected"),
    [(True, 200, True), (False, 403, False), (False, 404, False)],
)
@patch("mcp_zammad.client.ZammadAPI")
def test_can_access_ticket(mock_api: MagicMock, ok: bool, status_code: int, expected: bool) -> None:
    """403 and 404 mean the user cannot read the ticket; 2xx means they can."""
    mock_api.return_value.url = "https://test.zammad.com/api/v1/"
    client = ZammadClient(url="https://test.zammad.com/api/v1", oauth2_token=_TEST_AUTH_VALUE)
    client.api.session = MagicMock()  # replaces the ResilientSession wrapper
    client.api.session.get.return_value = MagicMock(ok=ok, status_code=status_code)

    assert client.can_access_ticket(7) is expected
    assert client.api.session.get.call_args.args[0] == "https://test.zammad.com/api/v1/tickets/7"


@patch("mcp_zammad.client.ZammadAPI")
def test_can_access_ticket_raises_on_other_errors(mock_api: MagicMock) -> None:
    """Server errors must surface instead of silently hiding the ticket."""
    mock_api.return_value.url = "https://test.zammad.com/api/v1/"
    client = ZammadClient(url="https://test.zammad.com/api/v1", oauth2_token=_TEST_AUTH_VALUE)
    client.api.session = MagicMock()  # replaces the ResilientSession wrapper
    client.api.session.get.return_value = MagicMock(ok=False, status_code=500, text="boom")

    with pytest.raises(ZammadAPIError) as exc_info:
        client.can_access_ticket(7)
    assert exc_info.value.status_code == 500


@pytest.mark.parametrize("truthy", ["1", "true", "yes", "on"])
@patch("mcp_zammad.client.ZammadAPI")
def test_client_insecure_mode_from_env(mock_api: MagicMock, truthy: str) -> None:
    """Test that documented truthy values disable TLS verification."""
    mock_instance = mock_api.return_value

    with patch.dict(
        os.environ,
        {
            "ZAMMAD_URL": "https://test.zammad.com/api/v1",
            "ZAMMAD_HTTP_TOKEN": "test-token",
            "ZAMMAD_INSECURE": truthy,
        },
        clear=True,
    ):
        client = ZammadClient()

    assert client.insecure is True
    assert mock_instance.session.verify is False


@patch("mcp_zammad.client.ZammadAPI")
def test_client_insecure_mode_from_param(mock_api: MagicMock, caplog: pytest.LogCaptureFixture) -> None:
    """Test that insecure constructor flag disables TLS verification."""
    mock_instance = mock_api.return_value
    with caplog.at_level(logging.WARNING):
        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token=_TEST_AUTH_VALUE, insecure=True)

    assert client.insecure is True
    assert mock_instance.session.verify is False
    assert "TLS certificate verification is disabled" in caplog.text


@patch("mcp_zammad.client.ZammadAPI")
def test_client_insecure_mode_uses_connection_fallback(mock_api: MagicMock) -> None:
    """When ZammadAPI.session is absent, use _connection.session if present."""
    mock_instance = mock_api.return_value
    mock_instance.session = None
    fallback_session = MagicMock()
    mock_connection = MagicMock()
    mock_connection.session = fallback_session
    mock_instance._connection = mock_connection

    client = ZammadClient(
        url="https://test.zammad.com/api/v1",
        http_token=_TEST_AUTH_VALUE,
        insecure=True,
    )

    assert client.insecure is True
    assert fallback_session.verify is False


@patch("mcp_zammad.client.ZammadAPI")
def test_client_insecure_mode_raises_when_no_session(mock_api: MagicMock) -> None:
    """Raise ConfigException when insecure is set but no requests session is available."""
    mock_instance = mock_api.return_value
    mock_instance.session = None
    mock_instance._connection = None

    with pytest.raises(ConfigException, match="does not expose a"):
        ZammadClient(
            url="https://test.zammad.com/api/v1",
            http_token=_TEST_AUTH_VALUE,
            insecure=True,
        )


def test_url_validation_no_protocol() -> None:
    """Test that URL validation rejects URLs without protocol."""
    with (
        patch.dict(os.environ, {"ZAMMAD_URL": "test.zammad.com", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True),
        pytest.raises(ConfigException, match="must include protocol"),
    ):
        ZammadClient()


def test_url_validation_invalid_protocol() -> None:
    """Test that URL validation rejects non-http/https protocols."""
    with (
        patch.dict(os.environ, {"ZAMMAD_URL": "ftp://test.zammad.com", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True),
        pytest.raises(ConfigException, match="must use http or https"),
    ):
        ZammadClient()


def test_url_validation_no_hostname() -> None:
    """Test that URL validation rejects URLs without hostname."""
    with (
        patch.dict(os.environ, {"ZAMMAD_URL": "https://", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True),
        pytest.raises(ConfigException, match="must include a valid hostname"),
    ):
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


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("172.20.0.5", "private network"),
        ("169.254.10.1", "private network"),
        ("127.0.0.2", "local host"),
        ("[::1]", "local host"),
    ],
)
@patch("mcp_zammad.client.ZammadAPI")
def test_url_validation_classifies_ip_literals(mock_api: MagicMock, caplog, host: str, expected: str) -> None:
    """IP literals are classified by address range, not by string prefix."""
    with patch.dict(os.environ, {"ZAMMAD_URL": f"http://{host}", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True):
        ZammadClient()
        assert f"points to {expected}" in caplog.text


@pytest.mark.parametrize("host", ["172.5.0.1", "10.example.com"])
@patch("mcp_zammad.client.ZammadAPI")
def test_url_validation_ignores_public_and_named_hosts(mock_api: MagicMock, caplog, host: str) -> None:
    """A public 172.x address or a hostname that merely starts with digits is not flagged."""
    with patch.dict(os.environ, {"ZAMMAD_URL": f"http://{host}", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True):
        ZammadClient()
        assert "points to" not in caplog.text


@patch("mcp_zammad.client.ZammadAPI")
def test_download_attachment(mock_api: MagicMock) -> None:
    """Test downloading an attachment."""
    mock_instance = mock_api.return_value
    mock_instance.ticket_article_attachment.download.return_value = b"file content"

    with patch.dict(
        os.environ, {"ZAMMAD_URL": "https://test.zammad.com/api/v1", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True
    ):
        client = ZammadClient()
        result = client.download_attachment(123, 456, 789)

    assert result == b"file content"
    mock_instance.ticket_article_attachment.download.assert_called_once_with(789, 456, 123)


@patch("mcp_zammad.client.ZammadAPI")
def test_get_article_attachments(mock_api: MagicMock) -> None:
    """Test getting article attachments."""
    mock_instance = mock_api.return_value
    mock_instance.ticket_article.find.return_value = {
        "id": 456,
        "attachments": [
            {"id": 1, "filename": "test.pdf", "size": 1024},
            {"id": 2, "filename": "image.png", "size": 2048},
        ],
    }

    with patch.dict(
        os.environ, {"ZAMMAD_URL": "https://test.zammad.com/api/v1", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True
    ):
        client = ZammadClient()
        result = client.get_article_attachments(123, 456)

    assert len(result) == 2
    assert result[0]["filename"] == "test.pdf"
    assert result[1]["filename"] == "image.png"
    mock_instance.ticket_article.find.assert_called_once_with(456)


@patch("mcp_zammad.client.ZammadAPI")
def test_add_article_with_attachments(mock_api: MagicMock) -> None:
    """Test adding article with attachments."""
    mock_instance = mock_api.return_value
    mock_instance.ticket_article.create.return_value = {
        "id": 789,
        "ticket_id": 123,
        "body": "See attached",
        "attachments": [{"id": 1, "filename": "test.pdf", "size": 1024}],
    }

    attachments = [{"filename": "test.pdf", "data": "dGVzdA==", "mime-type": "application/pdf"}]

    with patch.dict(
        os.environ, {"ZAMMAD_URL": "https://test.zammad.com/api/v1", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True
    ):
        client = ZammadClient()
        result = client.add_article(ticket_id=123, body="See attached", attachments=attachments)

    assert result["id"] == 789
    mock_instance.ticket_article.create.assert_called_once()
    call_args = mock_instance.ticket_article.create.call_args[0][0]
    assert "attachments" in call_args
    assert call_args["attachments"] == attachments


@patch("mcp_zammad.client.ZammadAPI")
def test_add_article_without_attachments_backward_compat(mock_api: MagicMock) -> None:
    """Test adding article without attachments (backward compatibility)."""
    mock_instance = mock_api.return_value
    mock_instance.ticket_article.create.return_value = {"id": 789, "ticket_id": 123, "body": "Simple comment"}

    with patch.dict(
        os.environ, {"ZAMMAD_URL": "https://test.zammad.com/api/v1", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True
    ):
        client = ZammadClient()
        result = client.add_article(ticket_id=123, body="Simple comment")

    assert result["id"] == 789
    call_args = mock_instance.ticket_article.create.call_args[0][0]
    assert "attachments" not in call_args  # Should not include empty attachments


@patch("mcp_zammad.client.ZammadAPI")
def test_add_article_with_time_unit(mock_api: MagicMock) -> None:
    """Test adding article with time_unit for time accounting."""
    mock_instance = mock_api.return_value
    mock_instance.ticket_article.create.return_value = {"id": 789, "ticket_id": 123, "body": "Worked on this"}

    with patch.dict(
        os.environ, {"ZAMMAD_URL": "https://test.zammad.com/api/v1", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True
    ):
        client = ZammadClient()
        result = client.add_article(ticket_id=123, body="Worked on this", time_unit=45.5)

    assert result["id"] == 789
    call_args = mock_instance.ticket_article.create.call_args[0][0]
    assert call_args["time_unit"] == 45.5


@patch("mcp_zammad.client.ZammadAPI")
def test_add_article_without_time_unit_excludes_field(mock_api: MagicMock) -> None:
    """Test that time_unit is not included in payload when None."""
    mock_instance = mock_api.return_value
    mock_instance.ticket_article.create.return_value = {"id": 789, "ticket_id": 123, "body": "Simple comment"}

    with patch.dict(
        os.environ, {"ZAMMAD_URL": "https://test.zammad.com/api/v1", "ZAMMAD_HTTP_TOKEN": "token"}, clear=True
    ):
        client = ZammadClient()
        result = client.add_article(ticket_id=123, body="Simple comment")

    assert result["id"] == 789
    call_args = mock_instance.ticket_article.create.call_args[0][0]
    assert "time_unit" not in call_args
