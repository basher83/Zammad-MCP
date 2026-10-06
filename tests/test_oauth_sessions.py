"""Tests for per-user OAuth session isolation."""

from unittest.mock import patch

import pytest
from fastmcp import Client
from fastmcp.server.auth import AccessToken

from mcp_zammad.oauth_settings import OAuthSettings
from mcp_zammad.server import ZammadMCPServer

_STAMP = "2024-01-01T00:00:00Z"


def _enabled_env() -> dict[str, str]:
    """Return a complete OAuth environment for tests."""
    return {
        "ZAMMAD_MCP_OAUTH": "true",
        "MCP_TRANSPORT": "http",
        "MCP_PUBLIC_URL": "https://mcp.example.com",
        "ZAMMAD_URL": "https://zammad.example/api/v1",
        "ZAMMAD_OAUTH_CLIENT_ID": "zammad-client",
        "ZAMMAD_OAUTH_CLIENT_SECRET": "zammad-secret",
    }


def _oauth_server() -> ZammadMCPServer:
    """Return a server in OAuth mode without reading the developer environment."""
    disabled = OAuthSettings(enabled=False)
    with patch("mcp_zammad.server.OAuthSettings.from_env", return_value=disabled):
        server = ZammadMCPServer()
    server.oauth_settings = OAuthSettings.from_env(_enabled_env())
    return server


def _record(record_id: int, name: str, **extra: object) -> dict[str, object]:
    """Return one Zammad reference record."""
    body: dict[str, object] = {
        "id": record_id,
        "name": name,
        "active": True,
        "created_at": _STAMP,
        "updated_at": _STAMP,
    }
    body.update(extra)
    return body


class _UserDirectory:
    """Zammad double whose reference lists depend on the signed-in user."""

    def __init__(self, *_args: object, oauth2_token: str = "", **_kwargs: object) -> None:
        """Store the credential this directory belongs to."""
        self.oauth2_token = oauth2_token

    def get_groups(self) -> list[dict[str, object]]:
        """Return the groups visible to this user."""
        name = "Alpha" if self.oauth2_token == "user-a" else "Beta"
        return [_record(1, name)]

    def get_ticket_states(self) -> list[dict[str, object]]:
        """Return the states visible to this user."""
        name = "new" if self.oauth2_token == "user-a" else "open"
        return [_record(1, name, state_type_id=1)]

    def get_ticket_priorities(self) -> list[dict[str, object]]:
        """Return the priorities visible to this user."""
        name = "1 low" if self.oauth2_token == "user-a" else "3 high"
        return [_record(1, name)]


def _use_token(monkeypatch: pytest.MonkeyPatch, holder: dict[str, str]) -> None:
    """Point request authentication at the token in holder."""
    monkeypatch.setattr(
        "fastmcp.server.dependencies.get_access_token",
        lambda: AccessToken(token=holder["token"], client_id="test", scopes=["full"]),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "own", "other"),
    [
        ("zammad_list_groups", "Alpha", "Beta"),
        ("zammad_list_ticket_states", "new", "open"),
        ("zammad_list_ticket_priorities", "1 low", "3 high"),
    ],
)
async def test_reference_lists_stay_with_the_signed_in_user(
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    own: str,
    other: str,
) -> None:
    """Reference data loaded for one signed-in user is not shown to the next."""
    holder = {"token": "user-a"}
    _use_token(monkeypatch, holder)
    with patch("mcp_zammad.server.ZammadClient", _UserDirectory):
        server = _oauth_server()
        async with Client(server.mcp) as client:
            first = await client.call_tool(tool, {})
            holder["token"] = "user-b"
            second = await client.call_tool(tool, {})
    assert own in first.content[0].text
    assert other not in first.content[0].text
    assert other in second.content[0].text
    assert own not in second.content[0].text


def test_one_oauth_user_reuses_the_zammad_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated calls for one person keep the same Zammad client and its limiter."""
    _use_token(monkeypatch, {"token": "user-a"})
    server = _oauth_server()
    with patch("mcp_zammad.client.ZammadAPI"):
        first = server.get_client()
        second = server.get_client()
    assert first is second


def test_oauth_users_do_not_share_a_zammad_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each signed-in person gets a Zammad client for their own credential."""
    holder = {"token": "user-a"}
    _use_token(monkeypatch, holder)
    server = _oauth_server()
    with patch("mcp_zammad.client.ZammadAPI"):
        first = server.get_client()
        holder["token"] = "user-b"
        second = server.get_client()
    assert first is not second
    assert first.oauth2_token == "user-a"
    assert second.oauth2_token == "user-b"
