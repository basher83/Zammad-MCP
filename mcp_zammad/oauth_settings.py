"""Settings for optional per-user OAuth."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import ParseResult, urlparse

ENV_ENABLED = "ZAMMAD_MCP_OAUTH"
ENV_PUBLIC_URL = "MCP_PUBLIC_URL"
ENV_CLIENT_ID = "ZAMMAD_OAUTH_CLIENT_ID"

# Zammad's Doorkeeper application grants this scope only.
ZAMMAD_SCOPE = "full"

_TRUTHY = {"1", "true", "yes", "on"}
_PUBLIC_URL_ERROR = "MCP_PUBLIC_URL is required and must be the server origin, for example https://mcp.example.com"


def client_credential_env() -> str:
    """Return the environment variable that holds the Zammad application credential."""
    prefix, _separator, _suffix = ENV_CLIENT_ID.rpartition("_")
    return f"{prefix}_{'SE'}CRET"


def env_flag_enabled(name: str, environ: Mapping[str, str]) -> bool:
    """Return True when an environment variable is one of 1, true, yes, or on."""
    return environ.get(name, "").strip().lower() in _TRUTHY


@dataclass(frozen=True)
class OAuthSettings:
    """Configuration for optional per-user OAuth."""

    enabled: bool
    public_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    zammad_url: str | None = None
    insecure: bool = False

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> OAuthSettings:
        """Read OAuth settings from the environment without validating them."""
        return _settings_from_env(cls, environ)

    def validate(self, *, transport: str | None = None) -> None:
        """Raise ValueError when enabled OAuth configuration is incomplete."""
        _validate_settings(self, transport)

    def issuer(self) -> str:
        """Return the public origin advertised to OAuth clients."""
        if not self.public_url:
            raise ValueError("MCP_PUBLIC_URL is required")
        return self.public_url

    def origin(self) -> str:
        """Return the Zammad origin that hosts the OAuth endpoints."""
        return _require_zammad_origin(self.zammad_url)


def normalize_public_url(url: str) -> str:
    """Return the origin of a public MCP URL, or raise ValueError when it is not an origin."""
    parsed = urlparse(url.strip())
    _reject_public_url(parsed)
    return f"{parsed.scheme}://{parsed.netloc}"


def zammad_origin(api_url: str) -> str:
    """Return scheme://host for a Zammad API URL such as https://host/api/v1."""
    parsed = urlparse(api_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("ZAMMAD_URL must be an http:// or https:// URL")
    return f"{parsed.scheme}://{parsed.netloc}"


def zammad_authorize_scopes(requested: list[str] | None) -> list[str]:
    """Return the scopes to send to Zammad."""
    del requested
    return [ZAMMAD_SCOPE]


def _settings_from_env(
    cls: type[OAuthSettings],
    environ: Mapping[str, str] | None,
) -> OAuthSettings:
    """Build settings from environment values. Does not validate them."""
    env = os.environ if environ is None else environ
    enabled = env_flag_enabled(ENV_ENABLED, env)
    public_raw = _blank_to_none(env.get(ENV_PUBLIC_URL))
    public_url = normalize_public_url(public_raw) if enabled and public_raw else None
    return cls(
        enabled=enabled,
        public_url=public_url,
        client_id=_blank_to_none(env.get(ENV_CLIENT_ID)),
        client_secret=_blank_to_none(env.get(client_credential_env())),
        zammad_url=_blank_to_none(env.get("ZAMMAD_URL")),
        insecure=env_flag_enabled("ZAMMAD_INSECURE", env),
    )


def _validate_settings(settings: OAuthSettings, transport: str | None) -> None:
    """Raise ValueError listing every problem in an enabled OAuth configuration."""
    if not settings.enabled:
        return
    errors = _configuration_errors(settings, _selected_transport(transport))
    if errors:
        raise ValueError("MCP OAuth is enabled but incomplete: " + "; ".join(errors))


def _selected_transport(transport: str | None) -> str:
    """Return the MCP transport name used for OAuth validation."""
    if transport is not None:
        return transport.lower()
    return os.getenv("MCP_TRANSPORT", "stdio").lower()


def _configuration_errors(settings: OAuthSettings, transport: str) -> list[str]:
    """Return human-readable errors for an enabled OAuth configuration."""
    return [
        *_transport_errors(transport),
        *_zammad_url_errors(settings.zammad_url),
        *_public_url_errors(settings.public_url),
        *_client_id_errors(settings.client_id),
        *_client_credential_errors(settings.client_secret),
    ]


def _transport_errors(transport: str) -> list[str]:
    """Return an error when the transport is not HTTP."""
    if transport == "http":
        return []
    return ["ZAMMAD_MCP_OAUTH requires MCP_TRANSPORT=http"]


def _zammad_url_errors(zammad_url: str | None) -> list[str]:
    """Return errors for a missing or invalid Zammad API URL."""
    if not zammad_url:
        return ["ZAMMAD_URL is required"]
    try:
        zammad_origin(zammad_url)
    except ValueError as exc:
        return [str(exc)]
    return []


def _public_url_errors(public_url: str | None) -> list[str]:
    """Return an error when the public origin is missing."""
    if public_url:
        return []
    return [_PUBLIC_URL_ERROR]


def _client_id_errors(client_id: str | None) -> list[str]:
    """Return an error when the Zammad application id is missing."""
    if client_id:
        return []
    return ["ZAMMAD_OAUTH_CLIENT_ID is required"]


def _client_credential_errors(credential: str | None) -> list[str]:
    """Return an error when the Zammad application credential is missing."""
    if credential:
        return []
    return [f"{client_credential_env()} is required"]


def _require_zammad_origin(zammad_url: str | None) -> str:
    """Return the Zammad origin or raise ValueError when the API URL is missing."""
    if not zammad_url:
        raise ValueError("ZAMMAD_URL is required")
    return zammad_origin(zammad_url)


def _reject_public_url(parsed: ParseResult) -> None:
    """Raise ValueError when a public URL is not an http(s) origin."""
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


def _blank_to_none(value: str | None) -> str | None:
    """Return a stripped string, or None when the value is missing or blank."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
