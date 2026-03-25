"""Transparent PII-filtering proxy for ZammadClient.

Enabled via ``PII_FILTER_ENABLED=true`` environment variable.
When enabled, wraps the ZammadClient so that:

- **Tool results** (Zammad → Claude): PII in string/dict/list return values
  is replaced with consistent pseudonyms, e.g. ``[PERSON_1]``, ``[EMAIL_1]``.
- **Tool inputs** (Claude → Zammad): pseudonym tokens in string arguments are
  restored to their original values before the API call is made.

The vault is kept in-memory for the lifetime of the MCP server process — no
Redis required.  Uses ``llm-anon-core`` (install with the ``[pii]`` extra).
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def pii_filter_enabled() -> bool:
    """Return True when PII_FILTER_ENABLED is set to a truthy value."""
    return os.getenv("PII_FILTER_ENABLED", "").lower() in ("1", "true", "yes")


def _walk(value: Any, fn: Any) -> Any:
    """Recursively apply *fn* to every string in *value* (dict/list/str)."""
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, dict):
        return {k: _walk(v, fn) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(item, fn) for item in value]
    return value


class PIIFilteringClient:
    """Transparent proxy that adds PII anonymization around every ZammadClient call.

    Attribute access falls through to the wrapped client via ``__getattr__``.
    Callable attributes are wrapped so that:

    1. String arguments are de-anonymized (pseudonym → original) before the
       underlying method is called.
    2. String / dict / list return values are anonymized (original → pseudonym)
       before being returned to the MCP framework / Claude.

    Only enabled when ``PII_FILTER_ENABLED=true``.  All other behaviour is
    identical to the unwrapped ``ZammadClient``.
    """

    def __init__(self, client: Any) -> None:
        try:
            from llm_anon_core import (  # type: ignore[import]
                AnonymizationConfig,
                AnonymizerService,
                SessionVault,
                build_analyzer,
                build_anonymizer,
                deanonymize_text,
            )
        except ImportError as exc:
            raise ImportError(
                "PII filtering requires the llm-anon-core package. "
                "Install it with: uv sync --extra pii"
            ) from exc

        cfg = AnonymizationConfig()
        service = AnonymizerService(build_analyzer(cfg), build_anonymizer(), cfg)
        vault = SessionVault(session_id="mcp-session")

        # Use object.__setattr__ to bypass our own __getattr__ for private attrs
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_service", service)
        object.__setattr__(self, "_vault", vault)
        object.__setattr__(self, "_deanonymize_text", deanonymize_text)

        logger.info("PIIFilteringClient ready — PII anonymization active")

    # ------------------------------------------------------------------
    # Internal helpers (defined on the class so __getattr__ is not called)
    # ------------------------------------------------------------------

    def _anonymize(self, text: str) -> str:
        result = self._service.anonymize_text(text, self._vault)
        return result.anonymized_text

    def _deanonymize(self, text: str) -> str:
        result = self._deanonymize_text(text, self._vault)
        return result.restored_text

    # ------------------------------------------------------------------
    # Transparent proxy
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        attr = getattr(self._client, name)
        if not callable(attr):
            return attr

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # De-anonymize inputs: Claude may reference pseudonyms in tool args
            clean_args = tuple(_walk(a, self._deanonymize) for a in args)
            clean_kwargs = {k: _walk(v, self._deanonymize) for k, v in kwargs.items()}

            result = attr(*clean_args, **clean_kwargs)

            # Anonymize output: replace PII before Claude sees it
            return _walk(result, self._anonymize)

        return wrapper
