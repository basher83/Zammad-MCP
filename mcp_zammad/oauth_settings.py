"""Settings for optional per-user OAuth.

OAuth is off unless ``ZAMMAD_MCP_OAUTH`` is set. The static credential path
(API token, OAuth2 token, or username and password) stays the default.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

ENV_ENABLED = "ZAMMAD_MCP_OAUTH"
ENV_PUBLIC_URL = "MCP_PUBLIC_URL"
ENV_CLIENT_ID = "ZAMMAD_OAUTH_CLIENT_ID"
ENV_CLIENT_SECRET = "ZAMMAD_OAUTH_CLIENT_SECRET"

# Zammad's Doorkeeper application grants this scope only.
ZAMMAD_SCOPE = "full"

_TRUTHY = {"1", "true", "yes", "on"}


def env_flag_enabled(name: str, environ: Mapping[str, str]) -> bool:
    """Return True when an environment variable is one of 1, true, yes, or on."""
    return environ.get(name, "").strip().lower() in _TRUTHY


@dataclass(frozen=True)
class OAuthSettings:
    """Configuration for the optional Claude-compatible OAuth mode.

    Attributes:
        enabled: Whether per-user OAuth is turned on.
        public_url: Origin harnesses use to reach this server, without a path.
        client_id: Client id of the OAuth application registered in Zammad.
        client_secret: Client secret of that Zammad OAuth application.
        zammad_url: Zammad API base URL, including ``/api/v1``.
        insecure: Disable TLS verification for the Zammad API and OAuth calls.
    """

    enabled: bool
    public_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    zammad_url: str | None = None
    insecure: bool = False

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> OAuthSettings:
        """Read OAuth settings from the environment.

        Does not validate. Call ``validate`` before starting the OAuth server.
        """
        env = os.environ if environ is None else environ
        enabled = env_flag_enabled(ENV_ENABLED, env)
        public_raw = _blank_to_none(env.get(ENV_PUBLIC_URL))
        # Ignore a public URL unless OAuth is on, so a stray value cannot change the static path.
        public_url = normalize_public_url(public_raw) if enabled and public_raw else None
        return cls(
            enabled=enabled,
            public_url=public_url,
            client_id=_blank_to_none(env.get(ENV_CLIENT_ID)),
            client_secret=_blank_to_none(env.get(ENV_CLIENT_SECRET)),
            zammad_url=_blank_to_none(env.get("ZAMMAD_URL")),
            insecure=env_flag_enabled("ZAMMAD_INSECURE", env),
        )

    def validate(self, *, transport: str | None = None) -> None:
        """Raise ValueError when OAuth is enabled but the configuration is incomplete.

        Args:
            transport: MCP transport name. Defaults to ``MCP_TRANSPORT`` or ``stdio``.
        """
        if not self.enabled:
            return

        errors: list[str] = []
        selected = (transport if transport is not None else os.getenv("MCP_TRANSPORT", "stdio")).lower()
        if selected != "http":
            errors.append("ZAMMAD_MCP_OAUTH requires MCP_TRANSPORT=http")
        if not self.zammad_url:
            errors.append("ZAMMAD_URL is required")
        else:
            try:
                zammad_origin(self.zammad_url)
            except ValueError as exc:
                errors.append(str(exc))
        if not self.public_url:
            errors.append(
                "MCP_PUBLIC_URL is required and must be the server origin, "
                "for example https://mcp.example.com"
            )
        if not self.client_id:
            errors.append("ZAMMAD_OAUTH_CLIENT_ID is required")
        if not self.client_secret:
            errors.append("ZAMMAD_OAUTH_CLIENT_SECRET is required")
        if errors:
            raise ValueError("MCP OAuth is enabled but incomplete: " + "; ".join(errors))

    def issuer(self) -> str:
        """Return the public origin advertised to OAuth clients."""
        if not self.public_url:
            raise ValueError("MCP_PUBLIC_URL is required")
        return self.public_url

    def origin(self) -> str:
        """Return the Zammad origin that hosts ``/oauth``."""
        if not self.zammad_url:
            raise ValueError("ZAMMAD_URL is required")
        return zammad_origin(self.zammad_url)


def normalize_public_url(url: str) -> str:
    """Return the origin of a public MCP URL.

    Harnesses such as Claude.ai send the connector URL ``{origin}/mcp``.
    The resource identifier must match that URL exactly, so the configured
    value is the origin only.

    Raises:
        ValueError: If the URL is not an http(s) origin.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("MCP_PUBLIC_URL must be an http:// or https:// origin")
    if parsed.username or parsed.password:
        raise ValueError("MCP_PUBLIC_URL must not include userinfo")
    if parsed.query or parsed.fragment:
        raise ValueError("MCP_PUBLIC_URL must not include a query or fragment")
    path = parsed.path.rstrip("/")
    if path not in {"", "/"}:
        raise ValueError(
            "MCP_PUBLIC_URL must be the origin only, for example https://mcp.example.com. "
            "The harness connector URL is {MCP_PUBLIC_URL}/mcp."
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def zammad_origin(api_url: str) -> str:
    """Return ``scheme://host`` for a Zammad API URL such as ``https://host/api/v1``."""
    parsed = urlparse(api_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("ZAMMAD_URL must be an http:// or https:// URL")
    return f"{parsed.scheme}://{parsed.netloc}"


def zammad_authorize_scopes(requested: list[str] | None) -> list[str]:
    """Return the scopes to send to Zammad.

    Zammad grants only ``full``. Remote harnesses may also ask for
    ``offline_access``; that scope is not forwarded.
    """
    del requested
    return [ZAMMAD_SCOPE]


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
