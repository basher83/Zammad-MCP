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


# Fields whose values are structurally guaranteed to contain PII.
# These are anonymized by key name, bypassing Presidio's NLP detection.
_PII_FIELDS: dict[str, str] = {
    "email":     "EMAIL_ADDRESS",
    "login":     "EMAIL_ADDRESS",
    "customer":    "EMAIL_ADDRESS",  # expanded ticket field: customer email
    "owner":       "PERSON",        # expanded ticket field: owner login
    "from":        "EMAIL_ADDRESS", # article sender
    "to":          "EMAIL_ADDRESS", # article recipient
    "created_by":  "EMAIL_ADDRESS", # article created_by
    "firstname": "PERSON",
    "lastname":  "PERSON",
    "phone":     "PHONE_NUMBER",
    "mobile":    "PHONE_NUMBER",
    "fax":       "PHONE_NUMBER",
}


def _walk(value: Any, fn: Any, key: str | None = None) -> Any:
    """Recursively apply *fn* to every string in *value* (dict/list/str).

    When descending into a dict, the field key is passed to *fn* so it can
    apply stronger anonymization for known-PII fields.
    """
    if isinstance(value, str):
        return fn(value, key)
    if isinstance(value, dict):
        return {k: _walk(v, fn, key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(item, fn, key=key) for item in value]
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

        cfg = AnonymizationConfig(known_persons_min_length=6)
        cfg.entities.pop("DATE_TIME", None)  # Dates are not PII — keep them readable
        # Err on the side of over-anonymization: lower thresholds so borderline
        # detections (names in greetings, informal locations) are still masked.
        cfg.entities["PERSON"].confidence_threshold = 0.6
        cfg.entities["LOCATION"].confidence_threshold = 0.6
        cfg.entities["EMAIL_ADDRESS"].confidence_threshold = 0.7
        cfg.entities["PHONE_NUMBER"].confidence_threshold = 0.5
        analyzer, list_recognizer = build_analyzer(cfg)
        service = AnonymizerService(analyzer, build_anonymizer(), cfg)
        vault = SessionVault(session_id="mcp-session")

        # Use object.__setattr__ to bypass our own __getattr__ for private attrs
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_service", service)
        object.__setattr__(self, "_vault", vault)
        object.__setattr__(self, "_deanonymize_text", deanonymize_text)
        object.__setattr__(self, "_list_recognizer", list_recognizer)

        logger.info("PIIFilteringClient ready — PII anonymization active")

    # ------------------------------------------------------------------
    # Internal helpers (defined on the class so __getattr__ is not called)
    # ------------------------------------------------------------------

    def refresh_known_persons(self) -> int:
        """Fetch all Zammad users and update the known-persons recognizer.

        Returns the number of name terms loaded.
        """
        try:
            users = self._client.search_users("*", per_page=200, page=1)
            # Collect all pages
            all_users = list(users) if not isinstance(users, list) else users
            page = 2
            while True:
                batch = self._client.search_users("*", per_page=200, page=page)
                batch = list(batch) if not isinstance(batch, list) else batch
                if not batch:
                    break
                all_users.extend(batch)
                page += 1
        except Exception:
            logger.exception("Failed to fetch users for known-persons list")
            return 0

        names: list[str] = []
        for u in all_users:
            if isinstance(u, dict):
                for field in ("firstname", "lastname"):
                    v = u.get(field) or ""
                    if v.strip():
                        names.append(v.strip())
            else:
                for field in ("firstname", "lastname"):
                    v = getattr(u, field, None) or ""
                    if v.strip():
                        names.append(v.strip())

        self._list_recognizer.update(names)
        logger.info("Known-persons list refreshed: %d name terms from %d users", len(names), len(all_users))
        return len(names)

    def _anonymize(self, text: str, key: str | None = None) -> str:
        if key and (entity_type := _PII_FIELDS.get(key)) and text.strip():
            return self._vault.get_or_create_pseudonym(text, entity_type)
        result = self._service.anonymize_text(text, self._vault)
        return result.anonymized_text

    def _deanonymize(self, text: str, key: str | None = None) -> str:
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
