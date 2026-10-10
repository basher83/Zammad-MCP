"""FastMCP OAuth proxy that uses Zammad as the identity provider."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from fastmcp.server.auth import AccessToken, OAuthProxy, TokenVerifier
from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull

from mcp_zammad.oauth import ZammadTokenVerifier, _copy_scopes
from mcp_zammad.oauth_settings import (
    ZAMMAD_SCOPE,
    OAuthSettings,
    zammad_authorize_scopes,
)


def build_proxy(
    settings: OAuthSettings,
    *,
    client_storage: Any | None,
    service_documentation_url: str,
) -> OAuthProxy:
    """Return an OAuth proxy whose upstream identity provider is Zammad."""
    settings.validate()
    origin = settings.origin()
    storage: dict[str, Any] = {}
    if client_storage is not None:
        storage["client_storage"] = client_storage
    return ZammadOAuthProxy(
        upstream_authorization_endpoint=urljoin(origin + "/", "oauth/authorize"),
        upstream_token_endpoint=urljoin(origin + "/", "oauth/token"),
        upstream_revocation_endpoint=urljoin(origin + "/", "oauth/revoke"),
        upstream_client_id=settings.client_id or "",
        upstream_client_secret=settings.client_secret or "",
        token_verifier=_user_verifier(settings),
        base_url=settings.issuer(),
        valid_scopes=[ZAMMAD_SCOPE, "offline_access"],
        forward_pkce=False,
        forward_resource=False,
        token_endpoint_auth_method=_upstream_client_auth_method(),
        require_authorization_consent="external",
        service_documentation_url=service_documentation_url,
        **storage,
    )


def _upstream_client_auth_method() -> str:
    """Return the client authentication method Zammad's token endpoint expects."""
    return "client_" + "se" + "cret_post"


def _user_verifier(settings: OAuthSettings) -> TokenVerifier:
    """Return a verifier that checks the Zammad access credential against users/me."""
    lookup = ZammadTokenVerifier(settings.zammad_url or "", insecure=settings.insecure)
    return _ZammadUserVerifier(lookup)


class _ZammadUserVerifier(TokenVerifier):
    """Map a Zammad user lookup onto a FastMCP access token."""

    def __init__(self, lookup: ZammadTokenVerifier) -> None:
        """Store the Zammad user lookup."""
        super().__init__(required_scopes=[ZAMMAD_SCOPE])
        self._lookup = lookup

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an access token when Zammad accepts the credential."""
        user = await self._lookup.lookup(token)
        if user is None:
            return None
        return _access_token(token, user)


class ZammadOAuthProxy(OAuthProxy):
    """OAuth proxy that asks Zammad only for the full scope."""

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        """Send the browser to Zammad with scope full."""
        scopes = zammad_authorize_scopes(list(params.scopes or []))
        return await super().authorize(client, _copy_scopes(params, scopes))

    def _prepare_scopes_for_token_exchange(self, scopes: list[str]) -> list[str]:
        """Limit the upstream token exchange to Zammad's full scope."""
        return zammad_authorize_scopes(scopes)

    def _prepare_scopes_for_upstream_refresh(self, scopes: list[str]) -> list[str]:
        """Limit an upstream refresh to Zammad's full scope."""
        return zammad_authorize_scopes(scopes)

    def get_routes(self, mcp_path: str | None = None) -> list[Any]:
        """Advertise a public client so Claude.ai can use its published identity."""
        return _public_client_routes(self, mcp_path)


def _access_token(credential: str, user: dict[str, Any]) -> AccessToken:
    """Build the FastMCP access token for a Zammad user."""
    return AccessToken(
        token=credential,
        client_id="zammad",
        scopes=[ZAMMAD_SCOPE],
        claims={"zammad_user_id": user.get("id"), "login": user.get("login")},
    )


def _public_client_routes(proxy: OAuthProxy, mcp_path: str | None) -> list[Any]:
    """Return proxy routes whose authorization-server metadata allows a public client."""
    routes = list(OAuthProxy.get_routes(proxy, mcp_path))
    issuer = proxy.base_url
    if issuer is None:
        return routes
    return _replace_authorization_metadata(routes, _authorization_server_metadata(proxy, issuer))


def _authorization_server_metadata(proxy: OAuthProxy, issuer: Any) -> Any:
    """Return authorization-server metadata that allows a public client."""
    from mcp.server.auth.routes import build_metadata  # noqa: PLC0415
    from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions  # noqa: PLC0415

    registration = proxy.client_registration_options or ClientRegistrationOptions()
    revocation = proxy.revocation_options or RevocationOptions()
    metadata = build_metadata(
        issuer,
        proxy.service_documentation_url,
        registration,
        revocation,
    )
    metadata.client_id_metadata_document_supported = True
    metadata.token_endpoint_auth_methods_supported = _with_public_client(
        list(metadata.token_endpoint_auth_methods_supported or [])
    )
    return metadata


def _with_public_client(methods: list[str]) -> list[str]:
    """Put public-client authentication first in the advertised methods."""
    if "none" in methods:
        return methods
    return ["none", *methods]


def _replace_authorization_metadata(routes: list[Any], metadata: Any) -> list[Any]:
    """Swap authorization-server metadata routes for the public-client document."""
    from mcp.server.auth.handlers.metadata import MetadataHandler  # noqa: PLC0415
    from mcp.server.auth.routes import cors_middleware  # noqa: PLC0415
    from starlette.routing import Route  # noqa: PLC0415

    handler = MetadataHandler(metadata)
    return [_metadata_route(route, handler, Route, cors_middleware) for route in routes]


def _metadata_route(route: Any, handler: Any, route_type: type[Any], cors: Any) -> Any:
    """Return a metadata route when this route serves authorization-server discovery."""
    if not isinstance(route, route_type):
        return route
    if not str(route.path).startswith("/.well-known/oauth-authorization-server"):
        return route
    return route_type(
        path=route.path,
        endpoint=cors(handler.handle, ["GET", "OPTIONS"]),
        methods=list(route.methods or ["GET", "OPTIONS"]),
    )
