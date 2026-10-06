"""OAuth authorization server for remote MCP harnesses.

This module is imported only when ``ZAMMAD_MCP_OAUTH`` is enabled. Claude.ai,
and other harnesses that use the same OAuth profile, talk to this server.
The person who signs in does so at Zammad. Zammad's access token for that
person is what later Zammad API calls use.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import httpx
from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull

from mcp_zammad.oauth_settings import (
    ZAMMAD_SCOPE,
    OAuthSettings,
    zammad_authorize_scopes,
)

logger = logging.getLogger(__name__)

_HTTP_OK = 200
_USERINFO_TIMEOUT_SECONDS = 10.0
_SERVICE_DOCS = "https://github.com/sg-cloudhesive/Zammad-MCP/blob/main/docs/deployment/oauth-harnesses.md"


class ZammadTokenVerifier:
    """Confirm a Zammad access token by calling ``GET /users/me``.

    This is not a ``TokenVerifier`` subclass at import time so the module can
    be loaded in tests that only need the HTTP check. ``as_auth_verifier``
    builds the FastMCP verifier used by the OAuth proxy.
    """

    def __init__(self, api_url: str, *, insecure: bool = False) -> None:
        """Store the Zammad API base URL.

        Args:
            api_url: Zammad API base URL, including ``/api/v1``.
            insecure: Disable TLS verification when true.
        """
        self.api_url = api_url.rstrip("/")
        self.insecure = insecure

    async def lookup(self, token: str) -> dict[str, Any] | None:
        """Return the Zammad user for a bearer token, or None when it is rejected.

        The token value is never logged.
        """
        if not token:
            return None
        url = f"{self.api_url}/users/me"
        try:
            async with httpx.AsyncClient(timeout=_USERINFO_TIMEOUT_SECONDS, verify=not self.insecure) as client:
                response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError:
            logger.info("Zammad user lookup failed for the OAuth bearer token")
            return None
        if response.status_code != _HTTP_OK:
            logger.info("Zammad rejected the OAuth bearer token with HTTP %s", response.status_code)
            return None
        try:
            body = response.json()
        except ValueError:
            logger.info("Zammad user lookup returned a non-JSON body")
            return None
        if not isinstance(body, dict) or body.get("id") is None:
            logger.info("Zammad user lookup did not return a user id")
            return None
        return body


def build_zammad_oauth_proxy(settings: OAuthSettings, *, client_storage: Any | None = None) -> Any:
    """Build the FastMCP OAuth proxy that uses Zammad as the identity provider.

    Args:
        settings: Validated OAuth settings.
        client_storage: Optional FastMCP client storage. The default is FastMCP's
            encrypted file store.

    Returns:
        A ``ZammadOAuthProxy`` instance.
    """
    settings.validate()
    # Imported here so the default static-credential path does not load the proxy.
    from fastmcp.server.auth import AccessToken, OAuthProxy, TokenVerifier  # noqa: PLC0415

    class _Verifier(TokenVerifier):
        def __init__(self, lookup: ZammadTokenVerifier) -> None:
            super().__init__(required_scopes=[ZAMMAD_SCOPE])
            self._lookup = lookup

        async def verify_token(self, token: str) -> AccessToken | None:
            user = await self._lookup.lookup(token)
            if user is None:
                return None
            return AccessToken(
                token=token,
                client_id="zammad",
                scopes=[ZAMMAD_SCOPE],
                claims={
                    "zammad_user_id": user.get("id"),
                    "login": user.get("login"),
                },
            )

    class ZammadOAuthProxy(OAuthProxy):
        """OAuth proxy that asks Zammad only for the ``full`` scope."""

        async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
            """Send the browser to Zammad with scope ``full``."""
            narrowed = _copy_scopes(params, zammad_authorize_scopes(list(params.scopes or [])))
            return await super().authorize(client, narrowed)

        def _prepare_scopes_for_token_exchange(self, scopes: list[str]) -> list[str]:
            return zammad_authorize_scopes(scopes)

        def _prepare_scopes_for_upstream_refresh(self, scopes: list[str]) -> list[str]:
            return zammad_authorize_scopes(scopes)

        def get_routes(self, mcp_path: str | None = None) -> list[Any]:
            """Advertise a public client so Claude.ai can use its published identity.

            Claude.ai selects a Client ID Metadata Document only when the
            authorization server metadata sets ``client_id_metadata_document_supported``
            and includes ``none`` in ``token_endpoint_auth_methods_supported``.
            The SDK metadata lists confidential-client methods only. This adds
            ``none`` without removing them, so dynamic registration still works.
            """
            from mcp.server.auth.handlers.metadata import MetadataHandler  # noqa: PLC0415
            from mcp.server.auth.routes import build_metadata, cors_middleware  # noqa: PLC0415
            from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions  # noqa: PLC0415
            from starlette.routing import Route  # noqa: PLC0415

            routes = list(super().get_routes(mcp_path))
            if self.base_url is None:
                return routes
            registration = self.client_registration_options or ClientRegistrationOptions()
            revocation = self.revocation_options or RevocationOptions()
            metadata = build_metadata(
                self.base_url,
                self.service_documentation_url,
                registration,
                revocation,
            )
            metadata.client_id_metadata_document_supported = True
            methods = list(metadata.token_endpoint_auth_methods_supported or [])
            if "none" not in methods:
                methods.insert(0, "none")
            metadata.token_endpoint_auth_methods_supported = methods
            handler = MetadataHandler(metadata)
            updated: list[Any] = []
            for route in routes:
                if isinstance(route, Route) and route.path.startswith("/.well-known/oauth-authorization-server"):
                    updated.append(
                        Route(
                            path=route.path,
                            endpoint=cors_middleware(handler.handle, ["GET", "OPTIONS"]),
                            methods=list(route.methods or ["GET", "OPTIONS"]),
                        )
                    )
                else:
                    updated.append(route)
            return updated

    origin = settings.origin()
    verifier = _Verifier(ZammadTokenVerifier(settings.zammad_url or "", insecure=settings.insecure))
    storage_kwargs: dict[str, Any] = {}
    if client_storage is not None:
        storage_kwargs["client_storage"] = client_storage
    return ZammadOAuthProxy(
        upstream_authorization_endpoint=urljoin(origin + "/", "oauth/authorize"),
        upstream_token_endpoint=urljoin(origin + "/", "oauth/token"),
        upstream_revocation_endpoint=urljoin(origin + "/", "oauth/revoke"),
        upstream_client_id=settings.client_id or "",
        upstream_client_secret=settings.client_secret or "",
        token_verifier=verifier,
        base_url=settings.issuer(),
        valid_scopes=[ZAMMAD_SCOPE, "offline_access"],
        forward_pkce=False,
        forward_resource=False,
        token_endpoint_auth_method="client_secret_post",
        require_authorization_consent="external",
        service_documentation_url=_SERVICE_DOCS,
        **storage_kwargs,
    )


def _copy_scopes(params: AuthorizationParams, scopes: list[str]) -> AuthorizationParams:
    """Return authorization params whose scope list is ``scopes``."""
    model_copy = getattr(params, "model_copy", None)
    if callable(model_copy):
        updated: AuthorizationParams = model_copy(update={"scopes": scopes})
        return updated
    params.scopes = scopes
    return params


def resource_url_for(settings: OAuthSettings) -> str:
    """Return the MCP resource URL a harness enters as the connector URL."""
    return f"{settings.issuer().rstrip('/')}/mcp"
