"""Opt-in JSON Lines audit logging for security-relevant MCP operations.

Audit records never go to stdout so the MCP stdio transport stays clean.
Configuration is read from the environment at the composition boundary:

- ``ZAMMAD_AUDIT_LOG_ENABLED``: 1/true/yes/on enables auditing (default: off)
- ``ZAMMAD_AUDIT_LOG_DESTINATION``: ``stderr`` (default), ``file`` or ``syslog``
- ``ZAMMAD_AUDIT_LOG_FILE``: append target, required when destination is ``file``
"""

import json
import logging
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import SysLogHandler
from pathlib import Path
from typing import Any

AUDIT_LOGGER_NAME = "zammad.audit"
DESTINATIONS = frozenset({"stderr", "file", "syslog"})
REDACTED = "[REDACTED]"
SENSITIVE_KEY_FRAGMENTS = ("password", "passwd", "token", "secret", "authorization", "credential", "data")
_TRUTHY = frozenset({"1", "true", "yes", "on"})


class AuditConfigError(ValueError):
    """Raised when audit logging is enabled with an invalid configuration."""


@dataclass(frozen=True)
class AuditConfig:
    """Validated audit logging settings."""

    enabled: bool = False
    destination: str = "stderr"
    file_path: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AuditConfig":
        """Build a config from environment-style mapping; invalid enabled configs fail loudly."""
        enabled = env.get("ZAMMAD_AUDIT_LOG_ENABLED", "").strip().lower() in _TRUTHY
        if not enabled:
            return cls()
        destination = env.get("ZAMMAD_AUDIT_LOG_DESTINATION", "stderr").strip().lower()
        if destination not in DESTINATIONS:
            raise AuditConfigError(
                f"ZAMMAD_AUDIT_LOG_DESTINATION must be one of {sorted(DESTINATIONS)}, got {destination!r}"
            )
        file_value = env.get("ZAMMAD_AUDIT_LOG_FILE", "").strip()
        if destination == "file" and not file_value:
            raise AuditConfigError("ZAMMAD_AUDIT_LOG_FILE is required when ZAMMAD_AUDIT_LOG_DESTINATION=file")
        return cls(enabled=True, destination=destination, file_path=Path(file_value) if file_value else None)


def _is_sensitive_key(key: Any) -> bool:
    """Return whether a mapping key looks like it names a credential or payload.

    Args:
        key: Mapping key to inspect; coerced to a lowercase string.

    Returns:
        True when the key contains any fragment in ``SENSITIVE_KEY_FRAGMENTS``.
    """
    lowered = str(key).lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact(value: Any) -> Any:
    """Return a copy of ``value`` with values under sensitive keys replaced by a marker.

    Args:
        value: Arbitrary JSON-like value; mappings and sequences are walked recursively.

    Returns:
        The redacted copy, or ``value`` unchanged for scalars.
    """
    if isinstance(value, Mapping):
        return {k: REDACTED if _is_sensitive_key(k) else redact(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(item) for item in value]
    return value


def _build_handler(config: AuditConfig) -> logging.Handler:
    """Create the logging handler for the configured sink; stdout is never used.

    Args:
        config: Validated audit settings selecting the destination.

    Returns:
        A file, syslog, or stderr handler.
    """
    if config.destination == "file" and config.file_path is not None:
        config.file_path.parent.mkdir(parents=True, exist_ok=True)
        return logging.FileHandler(config.file_path, mode="a", encoding="utf-8")
    if config.destination == "syslog":
        return SysLogHandler()
    return logging.StreamHandler(sys.stderr)


class AuditLogger:
    """Emit structured JSON Lines audit records to the configured sink."""

    def __init__(self, config: AuditConfig, *, now: Callable[[], datetime] | None = None) -> None:
        """Configure the ``zammad.audit`` logger for the given settings.

        Args:
            config: Validated audit settings; a disabled config installs no handler.
            now: Optional. Clock returning timezone-aware datetimes, for deterministic tests.
        """
        self._config = config
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._logger = logging.getLogger(AUDIT_LOGGER_NAME)
        self._configure_logger()

    @property
    def enabled(self) -> bool:
        """Whether audit records are emitted."""
        return self._config.enabled

    def _configure_logger(self) -> None:
        """Replace any existing audit handlers so reconfiguration never duplicates output."""
        for handler in list(self._logger.handlers):
            self._logger.removeHandler(handler)
            handler.close()
        self._logger.propagate = False
        self._logger.setLevel(logging.INFO)
        if not self._config.enabled:
            return
        handler = _build_handler(self._config)
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)

    def log_event(
        self,
        event_type: str,
        action: str,
        *,
        success: bool,
        resource_type: str | None = None,
        resource_id: int | str | None = None,
        duration_ms: float | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        """Write one audit record; a no-op when auditing is disabled.

        Args:
            event_type: Category such as ``tool_call``, ``authentication`` or ``security_validation``.
            action: What was attempted, e.g. the tool name.
            success: Whether the action completed without error.
            resource_type: Optional. Kind of resource acted on.
            resource_id: Optional. Identifier of the resource acted on.
            duration_ms: Optional. Elapsed wall-clock time in milliseconds.
            details: Optional. Extra context; sensitive keys are redacted before writing.
        """
        if not self._config.enabled:
            return
        record: dict[str, Any] = {
            "timestamp": self._now().isoformat(),
            "event_type": event_type,
            "action": action,
            "success": success,
        }
        optional = {"resource_type": resource_type, "resource_id": resource_id, "duration_ms": duration_ms}
        record.update({key: value for key, value in optional.items() if value is not None})
        record["details"] = redact(dict(details or {}))
        self._logger.info(json.dumps(record, default=str))


def error_details(exc: BaseException) -> dict[str, str]:
    """Describe a failure by root-cause type only; messages may carry secrets.

    Args:
        exc: The caught exception; ``__cause__`` chains are followed to the root.

    Returns:
        A single-key mapping ``{"error_type": <class name>}``.
    """
    root = exc
    while root.__cause__ is not None:
        root = root.__cause__
    return {"error_type": type(root).__name__}
