"""Tests for optional per-user OAuth."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastmcp import FastMCP
from key_value.aio.stores.memory import MemoryStore
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_zammad.client import ZammadClient
from mcp_zammad.oauth import ZammadTokenVerifier, _copy_scopes, build_zammad_oauth_proxy, resource_url_for
from mcp_zammad.oauth_settings import (
    OAuthSettings,
    normalize_public_url,
    zammad_authorize_scopes,
    zammad_origin,
)
from mcp_zammad.server import ZammadMCPServer


def _enabled_env(**overrides: str) -> dict[str, str]:
    """Return a complete OAuth environment, with optional overrides."""
    env = {
        "ZAMMAD_MCP_OAUTH": "true",
        "MCP_TRANSPORT": "http",
        "MCP_PUBLIC_URL": "https://mcp.example.com",
        "ZAMMAD_URL": "https://zammad.example/api/v1",
        "ZAMMAD_OAUTH_CLIENT_ID": "zammad-client",
        "ZAMMAD_OAUTH_CLIENT_SECRET": "zammad-secret",
    }
    env.update(overrides)
    return env


def test_oauth_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Static credentials stay the only path until the flag is set."""
    monkeypatch.delenv("ZAMMAD_MCP_OAUTH", raising=False)
    settings = OAuthSettings.from_env()
    assert settings.enabled is False
    settings.validate(transport="stdio")


@pytest.mark.parametrize("flag", ["1", "true", "yes", "on", "TRUE"])
def test_oauth_flag_truthy_values(flag: str) -> None:
    """The enable flag accepts the same truthy values as the other switches."""
    settings = OAuthSettings.from_env(_enabled_env(ZAMMAD_MCP_OAUTH=flag))
    assert settings.enabled is True
    assert settings.public_url == "https://mcp.example.com"
    assert settings.issuer() == "https://mcp.example.com"
    assert settings.origin() == "https://zammad.example"


@pytest.mark.parametrize("flag", ["", "0", "false", "no", "off"])
def test_oauth_flag_ignores_other_values(flag: str) -> None:
    """Any other value leaves the static credential path in place."""
    settings = OAuthSettings.from_env(_enabled_env(ZAMMAD_MCP_OAUTH=flag))
    assert settings.enabled is False


def test_oauth_validate_reports_every_missing_requirement() -> None:
    """One error lists every missing OAuth setting."""
    settings = OAuthSettings(enabled=True)
    with pytest.raises(ValueError, match="MCP_TRANSPORT=http") as exc:
        settings.validate(transport="stdio")
    message = str(exc.value)
    assert "ZAMMAD_URL" in message
    assert "MCP_PUBLIC_URL" in message
    assert "ZAMMAD_OAUTH_CLIENT_ID" in message
    assert "ZAMMAD_OAUTH_CLIENT_SECRET" in message


def test_public_url_rejects_a_path() -> None:
    """The public URL is the origin. The connector URL adds /mcp."""
    with pytest.raises(ValueError, match="origin only"):
        normalize_public_url("https://mcp.example.com/mcp")


def test_public_url_strips_a_trailing_slash() -> None:
    """A trailing slash is the same origin."""
    assert normalize_public_url("https://mcp.example.com/") == "https://mcp.example.com"


def test_disabled_mode_ignores_a_bad_public_url() -> None:
    """A stray MCP_PUBLIC_URL does not affect the static path."""
    settings = OAuthSettings.from_env({"ZAMMAD_MCP_OAUTH": "false", "MCP_PUBLIC_URL": "not a url"})
    assert settings.enabled is False
    assert settings.public_url is None


def test_zammad_origin_drops_the_api_path() -> None:
    """OAuth endpoints live on the Zammad host, not under /api/v1."""
    assert zammad_origin("https://help.example/api/v1") == "https://help.example"


def test_upstream_scope_is_only_full() -> None:
    """Harness scopes such as offline_access are not sent to Zammad."""
    assert zammad_authorize_scopes(["full", "offline_access"]) == ["full"]
    assert zammad_authorize_scopes(None) == ["full"]


def test_copy_scopes_uses_model_copy() -> None:
    """Authorization params keep every field except the scope list."""
    original = SimpleNamespace(
        scopes=["offline_access"], state="abc", model_copy=lambda update: SimpleNamespace(**update)
    )
    # The helper prefers model_copy and returns that object unchanged aside from scopes.
    copied = _copy_scopes(original, ["full"])  # type: ignore[arg-type]
    assert copied.scopes == ["full"]


def test_resource_url_is_the_mcp_connector_url() -> None:
    """Claude.ai must be given this exact URL."""
    settings = OAuthSettings.from_env(_enabled_env())
    assert resource_url_for(settings) == "https://mcp.example.com/mcp"


class _FakeResponse:
    """HTTP response double for the Zammad user lookup."""

    def __init__(self, status_code: int, body: object) -> None:
        """Store the status code and body the lookup will see."""
        self.status_code = status_code
        self._body = body

    def json(self) -> object:
        """Return the body, or raise it when the body is an exception."""
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class _FakeClient:
    """HTTP client double that records the user lookup request."""

    def __init__(self, response: _FakeResponse) -> None:
        """Store the response returned for every request."""
        self.response = response
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def __aenter__(self) -> "_FakeClient":
        """Enter the async client context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Leave the async client context without suppressing exceptions."""

    async def get(self, url: str, headers: dict[str, str]) -> _FakeResponse:
        """Record one GET and return the prepared response."""
        self.calls.append((url, headers))
        return self.response


@pytest.mark.asyncio
async def test_verifier_accepts_the_signed_in_zammad_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Zammad 200 for users/me binds the bearer token to that user."""
    fake = _FakeClient(_FakeResponse(200, {"id": 9, "login": "agent@example.com"}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *_args, **_kwargs: fake)
    verifier = ZammadTokenVerifier("https://zammad.example/api/v1/")
    user = await verifier.lookup("zammad-user-token")
    assert user is not None
    assert user["id"] == 9
    assert fake.calls[0][0] == "https://zammad.example/api/v1/users/me"
    assert fake.calls[0][1]["Authorization"] == "Bearer zammad-user-token"


@pytest.mark.asyncio
async def test_verifier_rejects_an_unauthorized_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zammad 401 means this bearer token is not a Zammad user."""
    fake = _FakeClient(_FakeResponse(401, {"error": "unauthorized"}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *_args, **_kwargs: fake)
    verifier = ZammadTokenVerifier("https://zammad.example/api/v1")
    assert await verifier.lookup("nope") is None


@pytest.mark.asyncio
async def test_verifier_rejects_a_body_without_a_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 that is not a Zammad user record is not accepted."""
    fake = _FakeClient(_FakeResponse(200, {"ok": True}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *_args, **_kwargs: fake)
    verifier = ZammadTokenVerifier("https://zammad.example/api/v1")
    assert await verifier.lookup("token") is None


@patch("mcp_zammad.client.ZammadAPI")
def test_per_user_client_ignores_the_static_token(mock_api: MagicMock) -> None:
    """The signed-in user's token wins over ZAMMAD_HTTP_TOKEN in the environment."""
    with patch.dict(
        os.environ,
        {
            "ZAMMAD_URL": "https://zammad.example/api/v1",
            "ZAMMAD_HTTP_TOKEN": "shared-service-token",
        },
        clear=True,
    ):
        client = ZammadClient(
            url="https://zammad.example/api/v1",
            oauth2_token="user-zammad-token",
            use_env_credentials=False,
        )
    assert client.oauth2_token == "user-zammad-token"
    assert client.http_token is None
    assert mock_api.call_args.kwargs["http_token"] is None
    assert mock_api.call_args.kwargs["oauth2_token"] == "user-zammad-token"


def _server_with_static_startup() -> ZammadMCPServer:
    """Build a server whose startup ignores OAuth in the process environment."""
    disabled = OAuthSettings(enabled=False)
    with patch("mcp_zammad.server.OAuthSettings.from_env", return_value=disabled):
        return ZammadMCPServer()


def test_get_client_uses_the_signed_in_zammad_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tool calls inherit the Zammad user who completed OAuth."""
    server = _server_with_static_startup()
    server.oauth_settings = OAuthSettings.from_env(_enabled_env())
    monkeypatch.setattr(
        "fastmcp.server.dependencies.get_access_token",
        lambda: SimpleNamespace(token="user-zammad-token"),
    )
    with (
        patch("mcp_zammad.client.ZammadAPI") as mock_api,
        patch.dict(os.environ, {"ZAMMAD_HTTP_TOKEN": "shared-service-token", "ZAMMAD_URL": "https://other/api/v1"}),
    ):
        client = server.get_client()
    assert client.url == "https://zammad.example/api/v1"
    assert client.oauth2_token == "user-zammad-token"
    assert client.http_token is None
    assert server.client is None
    assert mock_api.call_args.kwargs["oauth2_token"] == "user-zammad-token"


def test_get_client_requires_a_signed_in_user() -> None:
    """OAuth mode does not fall back to a shared Zammad credential."""
    server = _server_with_static_startup()
    server.oauth_settings = OAuthSettings.from_env(_enabled_env())
    with (
        patch("fastmcp.server.dependencies.get_access_token", return_value=None),
        pytest.raises(RuntimeError, match="not signed in"),
    ):
        server.get_client()


def test_discovery_matches_claude_ai_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Authorization-server metadata includes the fields Claude.ai requires."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    settings = OAuthSettings.from_env(_enabled_env())
    proxy = build_zammad_oauth_proxy(settings, client_storage=MemoryStore())
    app = Starlette(routes=proxy.get_routes("/mcp"))
    with TestClient(app) as client:
        metadata = client.get("/.well-known/oauth-authorization-server")
        resource = client.get("/.well-known/oauth-protected-resource/mcp")
    assert metadata.status_code == 200
    body = metadata.json()
    assert body["client_id_metadata_document_supported"] is True
    assert "none" in body["token_endpoint_auth_methods_supported"]
    assert "S256" in body["code_challenge_methods_supported"]
    assert body["registration_endpoint"].endswith("/register")
    assert body["authorization_endpoint"].endswith("/authorize")
    assert body["token_endpoint"].endswith("/token")
    assert body["service_documentation"].endswith("/docs/deployment/oauth-harnesses.md")
    assert "basher83/Zammad-MCP" in body["service_documentation"]
    assert body["code_challenge_methods_supported"] == ["S256"]
    assert resource.status_code == 200
    resource_body = resource.json()
    assert resource_body["resource"] == "https://mcp.example.com/mcp"
    assert resource_body["authorization_servers"][0].rstrip("/") == "https://mcp.example.com"
    assert resource_body["bearer_methods_supported"] == ["header"]


def test_unauthenticated_mcp_request_points_claude_at_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing bearer token is a 401 with the protected-resource metadata URL."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    settings = OAuthSettings.from_env(_enabled_env())
    proxy = build_zammad_oauth_proxy(settings, client_storage=MemoryStore())
    app = FastMCP("zammad_oauth_probe", auth=proxy).http_app(path="/mcp")
    with TestClient(app) as client:
        response = client.get("/mcp", headers={"Accept": "application/json, text/event-stream"})
    assert response.status_code == 401
    www = response.headers["www-authenticate"]
    assert 'resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource/mcp"' in www


@pytest.mark.asyncio
async def test_initialize_does_not_connect_a_shared_account(monkeypatch: pytest.MonkeyPatch) -> None:
    """Startup in OAuth mode waits for a person to sign in."""
    monkeypatch.setenv("ZAMMAD_MCP_OAUTH", "true")
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_PUBLIC_URL", "https://mcp.example.com")
    monkeypatch.setenv("ZAMMAD_URL", "https://zammad.example/api/v1")
    monkeypatch.setenv("ZAMMAD_OAUTH_CLIENT_ID", "zammad-client")
    monkeypatch.setenv("ZAMMAD_OAUTH_CLIENT_SECRET", "zammad-secret")
    sentinel = object()
    with patch("mcp_zammad.oauth.build_zammad_oauth_proxy", return_value=sentinel):
        server = ZammadMCPServer()
    assert server.mcp.auth is sentinel
    with patch.object(server, "_create_client") as create:
        await server.initialize()
    create.assert_not_called()
    assert server.client is None
