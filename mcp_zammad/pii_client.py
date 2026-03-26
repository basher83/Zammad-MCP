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
import re
from typing import Any

# Matches product/model codes like DC485S, MH1504P, DC640S.
# Pattern: 1-4 uppercase letters + 2+ digits + optional uppercase letter.
# This prevents spaCy from falsely classifying alphanumeric codes as PERSON.
_PRODUCT_CODE_RE = re.compile(r"\b[A-Z]{1,4}\d{2,}[A-Z]?\b")

# Additional product/brand names that don't match the alphanumeric regex above.
# Two sources, merged at startup:
#   PII_PRODUCT_NAMES_FILE — path to a text file, one name per line,
#                            lines starting with # are comments.
#   PII_PRODUCT_NAMES      — comma-separated fallback / quick overrides.
def _load_extra_product_names() -> frozenset[str]:
    import sys
    from pathlib import Path

    names: set[str] = set()
    # File source — default to product_names.txt next to this module
    _default = str(Path(__file__).parent / "product_names.txt")
    path = os.getenv("PII_PRODUCT_NAMES_FILE", _default)
    if path:
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        names.add(line)
        except OSError as exc:
            print(f"[pii_client] WARNING: cannot read PII_PRODUCT_NAMES_FILE {path!r}: {exc}", file=sys.stderr)
    # Env-var source (comma-separated)
    for name in os.getenv("PII_PRODUCT_NAMES", "").split(","):
        name = name.strip()
        if name:
            names.add(name)
    return frozenset(names)

_EXTRA_PRODUCT_NAMES: frozenset[str] = _load_extra_product_names()

# URLs must never be (partially) masked — replace them with null-byte placeholders
# before Presidio runs, then restore afterward.
_URL_RE = re.compile(r'https?://[^\s<>"\']+')

# Words that must never be anonymized even if spaCy detects them.
# These are passed as Presidio allow_list entries so NLP results for them are dropped.
# Lower-cased; matched case-insensitively against the actual text at anonymization time.
_STOPWORDS: frozenset[str] = frozenset({
    # Generic account names
    "admin", "administrator", "support", "helpdesk", "service",
    "system", "test", "demo", "guest", "user", "unknown",
    "team", "group", "partner", "logistics", "transport",
    "info", "noreply", "no-reply", "postmaster", "webmaster",
    # Common German words that appear as user fields in Zammad
    "nicht", "kein", "keine", "nein", "null", "leer",
    # Company/brand names registered as Zammad users — not person names
    "picoquant", "nikon", "zeiss", "abberior", "etsc", "opton", "crisel",
    "distex", "shipping", "tracking",
    # Common words that are also valid German/English surnames
    "blank", "stage", "gross", "klein", "braun", "weiss", "black",
    "white", "brown", "green", "young", "king", "new",
    # Month names (EN + DE) — appear as surnames but cause false positives
    "january", "february", "march", "april", "june", "july",
    "august", "september", "october", "november", "december",
    "januar", "februar", "maerz", "juni", "juli",
    "oktober", "dezember",
})

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

        cfg = AnonymizationConfig(known_persons_min_length=5)
        cfg.entities.pop("DATE_TIME", None)   # Dates are not PII — keep them readable
        cfg.entities.pop("LOCATION", None)   # Too many false positives (product names, German words)
        # Err on the side of over-anonymization: lower thresholds so borderline
        # detections (names in greetings, informal locations) are still masked.
        # Name list handles known persons — NLP is just a safety net, so keep
        # thresholds high to avoid product codes / common words being flagged.
        cfg.entities["PERSON"].confidence_threshold = 0.85
        cfg.entities["EMAIL_ADDRESS"].confidence_threshold = 0.7
        cfg.entities["PHONE_NUMBER"].confidence_threshold = 0.5
        analyzer, list_recognizer = build_analyzer(cfg)
        service = AnonymizerService(analyzer, build_anonymizer(), cfg)
        vault = SessionVault(session_id="mcp-session")

        # Pre-warm spaCy models and Presidio's internal language graph.
        # The very first analyze() call triggers lazy initialization which can
        # cause it to miss results — dummy calls here ensure real calls work
        # correctly from the first request onward.
        dummy_vault = SessionVault(session_id="warmup")
        _WARMUP_TEXTS = [
            "John Doe called jane@example.com about the invoice.",       # English
            "Hans Müller schrieb an beispiel@test.de wegen der Rechnung.",  # German
        ]
        for text in _WARMUP_TEXTS:
            try:
                service.anonymize_text(text, dummy_vault)
            except Exception:
                pass

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

    @staticmethod
    def _extract_names(users: list[Any], stopwords: set[str]) -> list[str]:
        names: list[str] = []
        for u in users:
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
        return [n for n in names if n.lower() not in stopwords]

    def refresh_known_persons(self) -> int:
        """Fetch all Zammad users and update the known-persons recognizer.

        Loads the first page immediately so PII filtering is active within
        seconds of startup, then fetches remaining pages and reloads the full
        list.  Returns the total number of name terms loaded.
        """
        try:
            first_page = self._client.search_users("*", per_page=200, page=1)
            first_page = list(first_page) if not isinstance(first_page, list) else first_page
        except Exception:
            logger.exception("Failed to fetch users for known-persons list")
            return 0

        # Quick load: make the first page available immediately so the very
        # first request after startup already has some PII filtering active.
        self._list_recognizer.update(self._extract_names(first_page, _STOPWORDS))
        logger.info("Known-persons list: quick-loaded %d users (page 1)", len(first_page))

        # Fetch remaining pages and do a full reload.
        all_users = list(first_page)
        page = 2
        try:
            while True:
                batch = self._client.search_users("*", per_page=200, page=page)
                batch = list(batch) if not isinstance(batch, list) else batch
                if not batch:
                    break
                all_users.extend(batch)
                page += 1
        except Exception:
            logger.exception("Failed to fetch remaining user pages")

        names = self._extract_names(all_users, _STOPWORDS)
        self._list_recognizer.update(names)
        logger.info("Known-persons list refreshed: %d name terms from %d users", len(names), len(all_users))
        return len(names)

    def _anonymize(self, text: str, key: str | None = None) -> str:
        if key and (entity_type := _PII_FIELDS.get(key)) and text.strip():
            return self._vault.get_or_create_pseudonym(text, entity_type)

        # Step 1: protect URLs by replacing them with null-byte placeholders.
        # This prevents any word inside a URL from being anonymized.
        _url_map: dict[str, str] = {}

        def _protect_url(m: re.Match[str]) -> str:
            ph = f"\x00URL{len(_url_map)}\x00"
            _url_map[ph] = m.group()
            return ph

        protected = _URL_RE.sub(_protect_url, text)

        # Step 2: build allow_list — Presidio will skip any detected entity
        # whose exact matched text appears in this list.
        allow_list: list[str] = []
        allow_list.extend(_PRODUCT_CODE_RE.findall(protected))
        allow_list.extend(n for n in _EXTRA_PRODUCT_NAMES if n in protected)
        # Add each stopword occurrence as-is (case-preserved) so NLP detections
        # for company/generic names are suppressed even at high spaCy confidence.
        for sw in _STOPWORDS:
            for m in re.finditer(re.escape(sw), protected, re.IGNORECASE):
                allow_list.append(m.group())

        result = self._service.anonymize_text(protected, self._vault, allow_list=allow_list or None)

        # Step 3: restore URLs
        anon = result.anonymized_text
        for ph, url in _url_map.items():
            anon = anon.replace(ph, url)
        return anon

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
