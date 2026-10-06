"""OAuth authorization server for remote MCP harnesses."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from mcp.server.auth.provider import AuthorizationParams

from mcp_zammad.oauth_settings import OAuthSettings

logger = logging.getLogger(__name__)

_HTTP_OK = 200
_USERINFO_TIMEOUT_SECONDS = 10.0
_SERVICE_DOCS = "https://github.com/basher83/Zammad-MCP/blob/main/docs/deployment/oauth-harnesses.md"


class ZammadTokenVerifier:
    """Confirm a Zammad access credential by calling GET /users/me."""

    def __init__(self, api_url: str, *, insecure: bool = False) -> None:
        """Store the Zammad API base URL."""
        self.api_url = api_url.rstrip("/")
        self.insecure = insecure

    async def lookup(self, token: str) -> dict[str, Any] | None:
        """Return the Zammad user for an access credential, or None when Zammad rejects it."""
        if not token:
            return None
        try:
            response = await _fetch_current_user(self.api_url, token, insecure=self.insecure)
        except httpx.HTTPError:
            logger.info("Zammad user lookup failed")
            return None
        return _user_from_response(response)


def build_zammad_oauth_proxy(settings: OAuthSettings, *, client_storage: Any | None = None) -> Any:
    """Build the FastMCP OAuth proxy that uses Zammad as the identity provider."""
    from mcp_zammad.oauth_proxy import build_proxy  # noqa: PLC0415

    return build_proxy(settings, client_storage=client_storage, service_documentation_url=_SERVICE_DOCS)


def _copy_scopes(params: AuthorizationParams, scopes: list[str]) -> AuthorizationParams:
    """Return authorization params whose scope list is scopes."""
    model_copy = getattr(params, "model_copy", None)
    if callable(model_copy):
        updated: AuthorizationParams = model_copy(update={"scopes": scopes})
        return updated
    params.scopes = scopes
    return params


def resource_url_for(settings: OAuthSettings) -> str:
    """Return the MCP resource URL a harness enters as the connector URL."""
    return f"{settings.issuer().rstrip('/')}/mcp"


async def _fetch_current_user(api_url: str, credential: str, *, insecure: bool) -> httpx.Response:
    """GET the current Zammad user with the caller's credential."""
    url = f"{api_url}/users/me"
    headers = {"Authorization": f"Bearer {credential}"}
    async with httpx.AsyncClient(timeout=_USERINFO_TIMEOUT_SECONDS, verify=not insecure) as client:
        return await client.get(url, headers=headers)


def _user_from_response(response: httpx.Response) -> dict[str, Any] | None:
    """Return the user body when Zammad accepted the lookup."""
    if response.status_code != _HTTP_OK:
        logger.info("Zammad rejected the signed-in user lookup with HTTP %s", response.status_code)
        return None
    body = _json_object(response)
    if body is None or body.get("id") is None:
        _log_missing_user_id(body)
        return None
    return body


def _log_missing_user_id(body: dict[str, Any] | None) -> None:
    """Log a user lookup that returned JSON without a user id."""
    if body is not None:
        logger.info("Zammad user lookup did not return a user id")


def _json_object(response: httpx.Response) -> dict[str, Any] | None:
    """Return a JSON object body, or None when the body is not JSON."""
    try:
        body = response.json()
    except ValueError:
        logger.info("Zammad user lookup returned a non-JSON body")
        return None
    if not isinstance(body, dict):
        logger.info("Zammad user lookup did not return a user id")
        return None
    return body
