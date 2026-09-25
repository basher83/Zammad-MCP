"""Environment-backed configuration for client-side rate limiting, retries, and circuit breaking."""

from __future__ import annotations

import os
from dataclasses import dataclass

from zammad_py.exceptions import ConfigException

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"", "0", "false", "no", "off"}


def _read_bool(name: str) -> bool:
    """Parse a boolean environment variable, rejecting unrecognised values."""
    value = os.getenv(name, "").strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigException(f"{name} must be one of 1/true/yes/on or 0/false/no/off, got {value!r}")


def _read_int(name: str, default: int, minimum: int) -> int:
    """Parse an integer environment variable that must be >= minimum."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigException(f"{name} must be an integer >= {minimum}, got {raw!r}") from exc
    if value < minimum:
        raise ConfigException(f"{name} must be an integer >= {minimum}, got {raw!r}")
    return value


def _read_positive_float(name: str, default: float) -> float:
    """Parse a floating-point environment variable that must be > 0."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigException(f"{name} must be a number > 0, got {raw!r}") from exc
    if value <= 0:
        raise ConfigException(f"{name} must be a number > 0, got {raw!r}")
    return value


@dataclass(frozen=True)
class ResilienceConfig:
    """Resolved resilience settings; rate limiting is opt-in, retries and circuit breaking are on."""

    rate_limit_enabled: bool = False
    rate_limit_requests: int = 60
    rate_limit_window: float = 60.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 30.0

    @classmethod
    def from_env(cls) -> ResilienceConfig:
        """Build the configuration from ZAMMAD_* environment variables.

        Raises:
            ConfigException: If any variable is present but not a valid value.
        """
        return cls(
            rate_limit_enabled=_read_bool("ZAMMAD_RATE_LIMIT_ENABLED"),
            rate_limit_requests=_read_int("ZAMMAD_RATE_LIMIT_REQUESTS", 60, minimum=1),
            rate_limit_window=_read_positive_float("ZAMMAD_RATE_LIMIT_WINDOW", 60.0),
            max_retries=_read_int("ZAMMAD_MAX_RETRIES", 3, minimum=0),
            retry_backoff_base=_read_positive_float("ZAMMAD_RETRY_BACKOFF_BASE", 1.0),
            circuit_failure_threshold=_read_int("ZAMMAD_CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5, minimum=1),
            circuit_recovery_timeout=_read_positive_float("ZAMMAD_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 30.0),
        )
