"""Zammad API client wrapper for the MCP server."""

import html as _html
import ipaddress
import logging
import os
import re as _re
from collections import deque
from datetime import date, datetime
from typing import Any
from urllib.parse import quote, urlparse

import requests
from zammad_py import ZammadAPI
from zammad_py.exceptions import ConfigException

from mcp_zammad.resilience import ResilientSession
from mcp_zammad.resilience_config import ResilienceConfig

from .audit import AuditLogger

logger = logging.getLogger(__name__)

# HTTP status codes used by the KB compatibility paths.
_HTTP_OK = 200
_HTTP_MULTIPLE_CHOICES = 300
_HTTP_NO_CONTENT = 204
_HTTP_FORBIDDEN = 403
_HTTP_NOT_FOUND = 404


def _is_2xx(status_code: int) -> bool:
    """Return True iff the HTTP status code is a 2xx success."""
    return _HTTP_OK <= status_code < _HTTP_MULTIPLE_CHOICES


class ZammadAPIError(Exception):
    """
    Raised when the Zammad API returns a non-2xx response.

    Exposes ``status_code``, ``url`` and ``body`` of the failing response so
    callers can react to specific error classes (e.g. 401/403/404/5xx).
    """

    def __init__(self, status_code: int, url: str, body: object) -> None:
        """Initialize a Zammad API error from response context."""
        self.status_code = status_code
        self.url = url
        self.body = body
        super().__init__(f"HTTP {status_code} from Zammad: {body} (URL: {url})")


# Direct session calls bypass zammad_py, which sets no timeout; bound them so a
# stalled Zammad server cannot hang a tool call indefinitely.
REQUEST_TIMEOUT_SECONDS = 30.0


class ZammadClient:
    """Wrapper around zammad_py ZammadAPI with additional functionality."""

    def __init__(
        self,
        url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        http_token: str | None = None,
        oauth2_token: str | None = None,
        *,
        insecure: bool | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        """Initialize Zammad client with environment variables or provided credentials.

        Supports reading secrets from files using Docker secrets pattern:
        - ZAMMAD_HTTP_TOKEN_FILE: Path to file containing HTTP token
        - ZAMMAD_OAUTH2_TOKEN_FILE: Path to file containing OAuth2 token
        - ZAMMAD_PASSWORD_FILE: Path to file containing password

        Set insecure=True, or set ZAMMAD_INSECURE to 1/true/yes/on, only for
        trusted self-signed/internal certificate chains. Defaults to secure TLS
        verification.

        Pass audit_logger to receive security_validation events for URL checks.

        An explicit oauth2_token (the per-request token of an OAuth-authenticated
        user) suppresses the environment-derived static credentials. zammad_py
        prefers an HTTP token over an OAuth2 token, so a leftover ZAMMAD_HTTP_TOKEN
        would otherwise make every user act as the static account.
        """
        self._audit = audit_logger
        self.url = url or os.getenv("ZAMMAD_URL")

        if oauth2_token:
            self.username = username
            self.password = password
            self.http_token = http_token
            self.oauth2_token: str | None = oauth2_token
        else:
            self.username = username or os.getenv("ZAMMAD_USERNAME")
            # Try to read secrets from files first (Docker secrets pattern)
            self.password = password or self._read_secret_file("ZAMMAD_PASSWORD_FILE") or os.getenv("ZAMMAD_PASSWORD")
            self.http_token = (
                http_token or self._read_secret_file("ZAMMAD_HTTP_TOKEN_FILE") or os.getenv("ZAMMAD_HTTP_TOKEN")
            )
            self.oauth2_token = self._read_secret_file("ZAMMAD_OAUTH2_TOKEN_FILE") or os.getenv("ZAMMAD_OAUTH2_TOKEN")
        self.insecure = insecure if insecure is not None else ZammadClient._parse_bool_env("ZAMMAD_INSECURE")
        self.resilience = ResilienceConfig.from_env()

        if not self.url:
            raise ConfigException("Zammad URL is required. Set ZAMMAD_URL environment variable.")

        # Validate URL format to prevent SSRF
        self._validate_url(self.url)

        if not any([self.http_token, self.oauth2_token, (self.username and self.password)]):
            # Check if user mistakenly used ZAMMAD_TOKEN
            if os.getenv("ZAMMAD_TOKEN"):
                raise ConfigException(
                    "Found ZAMMAD_TOKEN but this server expects ZAMMAD_HTTP_TOKEN. "
                    "Please rename your environment variable from ZAMMAD_TOKEN to ZAMMAD_HTTP_TOKEN."
                )
            raise ConfigException(
                "Authentication credentials required. Set either ZAMMAD_HTTP_TOKEN, "
                "ZAMMAD_OAUTH2_TOKEN, or both ZAMMAD_USERNAME and ZAMMAD_PASSWORD."
            )

        self.api = ZammadAPI(
            url=self.url,
            username=self.username,
            password=self.password,
            http_token=self.http_token,
            oauth2_token=self.oauth2_token,
        )
        if self.insecure:
            # Allow connecting to instances with self-signed/missing CA certs.
            session = getattr(self.api, "session", None)
            if session is None:
                connection = getattr(self.api, "_connection", None)
                session = getattr(connection, "session", None) if connection is not None else None
            if session is None:
                msg = (
                    "ZAMMAD_INSECURE is enabled but the installed zammad-py client does not expose a "
                    "requests session; TLS verification cannot be disabled."
                )
                raise ConfigException(msg)
            session.verify = False
            logger.warning(
                "TLS certificate verification is disabled (ZAMMAD_INSECURE=true). "
                "urllib3 may emit InsecureRequestWarning on requests; fix or trust the server certificate when possible."
            )
        # zammad-py routes every resource call through this session, so wrapping it once
        # gives rate limiting, retries, and circuit breaking to all API operations.
        self.api.session = ResilientSession(self.api.session, self.resilience)

    def _validate_url(self, url: str) -> None:
        """Validate URL format to prevent SSRF attacks."""

        def _raise_config_error(message: str) -> None:
            """Helper to raise ConfigException."""
            raise ConfigException(message)

        try:
            parsed = urlparse(url)

            # Ensure URL has a scheme
            if not parsed.scheme:
                _raise_config_error("Zammad URL must include protocol (http:// or https://)")

            # Only allow http/https
            if parsed.scheme not in ["http", "https"]:
                _raise_config_error("Zammad URL must use http or https protocol")

            # Ensure URL has a hostname
            if not parsed.hostname:
                _raise_config_error("Zammad URL must include a valid hostname")

            self._check_host_network(parsed.hostname.lower() if parsed.hostname else "")

        except Exception as e:
            raise ConfigException(f"Invalid Zammad URL format: {e}") from e

    def _check_host_network(self, hostname: str) -> None:
        """Warn (and audit) when the Zammad host is local or on a private network.

        IP literals are classified by address range; other hostnames are left
        alone because their spelling says nothing about where they resolve.
        """
        reason = ZammadClient._classify_host(hostname)
        if reason is None:
            return
        logger.warning("Zammad URL points to %s: %s", reason.replace("_", " "), hostname)
        self._audit_host(reason, hostname)

    @staticmethod
    def _classify_host(hostname: str) -> str | None:
        """Return ``local_host``, ``private_network`` or None for a URL hostname."""
        if hostname == "localhost":
            return "local_host"
        try:
            ip = ipaddress.ip_address(hostname.strip("[]"))
        except ValueError:
            return None
        if ip.is_loopback or ip.is_unspecified:
            return "local_host"
        if ip.is_private or ip.is_link_local:
            return "private_network"
        return None

    def _audit_host(self, reason: str, hostname: str) -> None:
        """Emit a security_validation audit event carrying only the hostname, never the full URL."""
        if self._audit is None:
            return
        self._audit.log_event(
            "security_validation",
            "zammad_url_check",
            success=False,
            resource_type="zammad_url",
            details={"reason": reason, "host": hostname},
        )

    def _read_secret_file(self, env_var: str) -> str | None:
        """Read secret from file path specified in environment variable.

        Args:
            env_var: Name of environment variable containing the file path

        Returns:
            Secret content from file or None if not found/readable
        """
        secret_file = os.getenv(env_var)
        if not secret_file:
            return None

        try:
            with open(secret_file) as f:
                return f.read().strip()
        except OSError:
            logger.warning(f"Failed to read secret for environment variable '{env_var}'.")
            return None

    @staticmethod
    def _parse_bool_env(env_var: str) -> bool:
        """Parse common truthy values from environment variables."""
        value = os.getenv(env_var, "").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def search_tickets(
        self,
        query: str | None = None,
        state: str | None = None,
        priority: str | None = None,
        group: str | None = None,
        owner: str | None = None,
        customer: str | None = None,
        created_after: date | str | None = None,
        created_before: date | str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> list[dict[str, Any]]:
        """Search tickets with various filters.

        created_after and created_before bound the search by creation date, inclusive
        on both ends. Dates are passed to Zammad in ISO YYYY-MM-DD form.
        """
        filters = {"page": page, "per_page": per_page, "expand": "true"}

        # Build search query: each filter contributes one clause when set.
        clauses = [
            (query, "{}"),
            (state, "state.name:{}"),
            (priority, "priority.name:{}"),
            (group, "group.name:{}"),
            (owner, "owner.login:{}"),
            (customer, "customer.email:{}"),
            (created_after, "created_at:>={}"),
            (created_before, "created_at:<={}"),
        ]
        search_parts = [template.format(value) for value, template in clauses if value]

        if search_parts:
            search_query = " AND ".join(search_parts)
            result = self.api.ticket.search(search_query, filters=filters)
        else:
            result = self.api.ticket.all(filters=filters)

        return list(result)

    def list_tickets(self, page: int = 1, per_page: int = 50) -> list[dict[str, Any]]:
        """List tickets with pagination (no 10K search limit).

        Uses the list endpoint which has no result cap, unlike the search endpoint
        which is limited to 10,000 results.
        """
        filters = {"page": page, "per_page": per_page, "expand": True}
        result = self.api.ticket.all(filters=filters)
        return list(result)

    def _find_ticket_expanded(self, ticket_id: int) -> dict[str, Any]:
        """Fetch a single ticket with ``expand=true``.

        The expand value must be the lowercase string ``"true"`` — Zammad is
        case-sensitive here and ``requests`` serializes the bool ``True`` as
        ``"True"``, which Zammad ignores.

        Raises:
            requests.HTTPError: If the API request fails, carrying Zammad's
                response body so callers can detect "Couldn't find Ticket ..."
        """
        # self.api.url is zammad_py's normalised base (always ends in "/"), so a
        # trailing slash on ZAMMAD_URL cannot produce ".../api/v1//tickets/1".
        response = self.api.session.get(
            f"{self.api.url}tickets/{ticket_id}", params={"expand": "true"}, timeout=REQUEST_TIMEOUT_SECONDS
        )
        if not response.ok:
            raise requests.HTTPError(response.text)
        return dict(response.json())

    def can_access_ticket(self, ticket_id: int) -> bool:
        """Return whether the authenticated user may read the ticket.

        Zammad answers 403 for tickets outside the user's permissions and 404
        for deleted ones; both mean "no access". Other failures raise
        :class:`ZammadAPIError` rather than silently hiding the ticket.
        """
        response = self.api.session.get(f"{self.api.url}tickets/{ticket_id}", timeout=REQUEST_TIMEOUT_SECONDS)
        if response.ok:
            return True
        if response.status_code in (_HTTP_FORBIDDEN, _HTTP_NOT_FOUND):
            return False
        raise ZammadAPIError(response.status_code, response.url, response.text)

    def get_ticket(
        self, ticket_id: int, include_articles: bool = True, article_limit: int = 10, article_offset: int = 0
    ) -> dict[str, Any]:
        """Get a single ticket by ID with optional article pagination.

        Uses a direct HTTP call via zammad_py's internal session because
        ``Resource.find()`` accepts no filters, so there is no way to pass
        ``expand=true`` through it. Without expansion Zammad only returns the
        ``*_id`` fields and the state/priority/group/owner/customer names all
        render as "Unknown".
        """
        ticket = self._find_ticket_expanded(ticket_id)

        if include_articles:
            articles = self.api.ticket.articles(ticket_id)

            # Convert to list if needed
            articles_list = list(articles) if not isinstance(articles, list) else articles

            # Handle article pagination
            if article_limit == -1:  # -1 means get all articles
                ticket["articles"] = articles_list
            else:
                # Apply offset and limit
                start_idx = article_offset
                end_idx = start_idx + article_limit
                ticket["articles"] = articles_list[start_idx:end_idx]

        return dict(ticket)

    def create_ticket(
        self,
        title: str,
        group: str,
        customer: str,
        article_body: str,
        state: str = "new",
        priority: str = "2 normal",
        article_type: str = "note",
        article_internal: bool = False,
    ) -> dict[str, Any]:
        """Create a new ticket."""
        ticket_data = {
            "title": title,
            "group": group,
            "customer": customer,
            "state": state,
            "priority": priority,
            "article": {
                "body": article_body,
                "type": article_type,
                "internal": article_internal,
            },
        }

        return dict(self.api.ticket.create(ticket_data))

    def update_ticket(
        self,
        ticket_id: int,
        title: str | None = None,
        state: str | None = None,
        priority: str | None = None,
        owner: str | None = None,
        group: str | None = None,
        pending_time: datetime | str | None = None,
        time_unit: float | None = None,
        custom_fields: dict[str, Any] | None = None,
        customer: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing ticket.

        Args:
            ticket_id: Internal ticket ID.
            title: Optional. New ticket title.
            state: Optional. New state name.
            priority: Optional. New priority name.
            owner: Optional. New owner login/email.
            group: Optional. New group name.
            pending_time: Optional. Pending-until timestamp for pending states; datetimes are sent as ISO 8601.
            customer: Optional. New customer login/email.
            time_unit: Optional. Time spent for time accounting; must be > 0.
            custom_fields: Optional. Custom object attributes sent as top-level ticket keys.

        Returns:
            The updated ticket as returned by Zammad.

        Raises:
            ValueError: If time_unit is not positive or a custom field shadows a built-in key.
        """
        if time_unit is not None and time_unit <= 0:
            raise ValueError("time_unit must be greater than 0")

        # Zammad expects an ISO 8601 string; serialize datetimes for the JSON body.
        if isinstance(pending_time, datetime):
            pending_time = pending_time.isoformat()

        built_in = {
            "title": title,
            "state": state,
            "priority": priority,
            "owner": owner,
            "group": group,
            "customer": customer,
            "pending_time": pending_time,
            "time_unit": time_unit,
        }
        update_data: dict[str, Any] = {key: value for key, value in built_in.items() if value is not None}
        for name in custom_fields or {}:
            if name in built_in:
                raise ValueError(f"custom_fields key '{name}' is a built-in field; pass it as a named argument")
        update_data.update(custom_fields or {})

        return dict(self.api.ticket.update(ticket_id, update_data))

    def add_article(
        self,
        ticket_id: int,
        body: str,
        article_type: str = "note",
        internal: bool = False,
        sender: str = "Agent",
        time_unit: float | None = None,
        subject: str | None = None,
        to: str | None = None,
        cc: str | None = None,
        content_type: str | None = None,
        attachments: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Add an article (comment/note) to a ticket with optional attachments.

        Args:
            ticket_id: Ticket ID to add article to
            body: Article body content
            article_type: Article type (note, email, phone)
            internal: Whether the article is internal
            sender: Sender type (Agent, Customer, System)
            time_unit: Time spent for time accounting (unit defined in Zammad admin settings)
            subject: Optional email subject
            to: Optional email recipient
            cc: Optional email CC recipient(s)
            content_type: Optional content type (text/plain or text/html)
            attachments: Optional list of attachments with keys:
                - filename: str
                - data: str (base64-encoded content)
                - mime-type: str

        Returns:
            Created article data with attachment metadata
        """
        if time_unit is not None and time_unit <= 0:
            raise ValueError("time_unit must be greater than 0")

        article_data = {
            "ticket_id": ticket_id,
            "body": body,
            "type": article_type,
            "internal": internal,
            "sender": sender,
        }

        if time_unit is not None:
            article_data["time_unit"] = time_unit
        if subject is not None:
            article_data["subject"] = subject
        if to is not None:
            article_data["to"] = to
        if cc is not None:
            article_data["cc"] = cc
        if content_type is not None:
            article_data["content_type"] = content_type

        if attachments:
            article_data["attachments"] = attachments

        return dict(self.api.ticket_article.create(article_data))

    def get_user(self, user_id: int) -> dict[str, Any]:
        """Get user information by ID."""
        return dict(self.api.user.find(user_id))

    def search_users(
        self,
        query: str,
        page: int = 1,
        per_page: int = 25,
    ) -> list[dict[str, Any]]:
        """Search users."""
        filters = {"page": page, "per_page": per_page, "expand": "true"}
        result = self.api.user.search(query, filters=filters)
        return list(result)

    def create_user(
        self,
        email: str,
        firstname: str,
        lastname: str,
        login: str | None = None,
        phone: str | None = None,
        mobile: str | None = None,
        organization: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Create a new user in Zammad."""
        user_data: dict[str, Any] = {"email": email, "firstname": firstname, "lastname": lastname}
        if login:
            user_data["login"] = login
        if phone:
            user_data["phone"] = phone
        if mobile:
            user_data["mobile"] = mobile
        if organization:
            user_data["organization"] = organization
        if note:
            user_data["note"] = note
        return dict(self.api.user.create(user_data))

    def get_organization(self, org_id: int) -> dict[str, Any]:
        """Get organization information by ID."""
        return dict(self.api.organization.find(org_id))

    def search_organizations(
        self,
        query: str,
        page: int = 1,
        per_page: int = 25,
    ) -> list[dict[str, Any]]:
        """Search organizations."""
        filters = {"page": page, "per_page": per_page, "expand": "true"}
        result = self.api.organization.search(query, filters=filters)
        return list(result)

    def get_groups(self) -> list[dict[str, Any]]:
        """Get all groups."""
        result = self.api.group.all()
        return list(result)

    def get_ticket_states(self) -> list[dict[str, Any]]:
        """Get all ticket states."""
        result = self.api.ticket_state.all()
        return list(result)

    def get_ticket_priorities(self) -> list[dict[str, Any]]:
        """Get all ticket priorities."""
        result = self.api.ticket_priority.all()
        return list(result)

    def get_current_user(self) -> dict[str, Any]:
        """Get current authenticated user."""
        return dict(self.api.user.me())

    def get_ticket_tags(self, ticket_id: int) -> list[str]:
        """Get tags for a ticket."""
        tags = self.api.ticket.tags(ticket_id)
        return list(tags.get("tags", []))

    def add_ticket_tag(self, ticket_id: int, tag: str) -> dict[str, Any]:
        """Add a tag to a ticket.

        Returns:
            Dictionary with 'success' key (bool) and optional 'message' key.
            Format: {"success": True, "message": None}
        """
        result = self.api.ticket_tag.add(ticket_id, tag)
        # Zammad returns a boolean, convert to TagOperationResult format
        return {"success": result, "message": None}

    def remove_ticket_tag(self, ticket_id: int, tag: str) -> dict[str, Any]:
        """Remove a tag from a ticket.

        Returns:
            Dictionary with 'success' key (bool) and optional 'message' key.
            Format: {"success": True, "message": None}
        """
        result = self.api.ticket_tag.remove(ticket_id, tag)
        # Zammad returns a boolean, convert to TagOperationResult format
        return {"success": result, "message": None}

    def download_attachment(self, ticket_id: int, article_id: int, attachment_id: int) -> bytes:
        """Download an attachment from a ticket article."""
        result = self.api.ticket_article_attachment.download(attachment_id, article_id, ticket_id)
        return bytes(result)

    def get_article_attachments(self, _ticket_id: int, article_id: int) -> list[dict[str, Any]]:
        """Get list of attachments for a ticket article."""
        # Get the article with attachments
        article = self.api.ticket_article.find(article_id)
        attachments = article.get("attachments", [])
        return list(attachments)

    def list_tags(self) -> list[dict[str, Any]]:
        """Get all tags defined in the Zammad system.

        Uses direct HTTP call via zammad_py's internal session since
        the tag_list endpoint is not exposed by the library.

        Note:
            Requires admin.tag permission.

        Returns:
            List of tag objects with id, name, and count fields.

        Raises:
            requests.HTTPError: If the API request fails (e.g., 403 Forbidden)
        """
        # Use zammad_py's internal session for authentication
        response = self.api.session.get(f"{self.url}/tag_list")
        response.raise_for_status()
        return list(response.json())

    # ------------------------------------------------------------------
    # Knowledge Base methods (direct HTTP - not covered by zammad_py).
    # Read-only operations only; writes/attachments land in follow-up PRs.
    # ------------------------------------------------------------------

    def _kb_url(self, *parts: str | int) -> str:
        """Build a knowledge-base API URL from path components."""
        path = "/".join(str(p) for p in parts)
        return f"{self.api.url}knowledge_bases/{path}"

    def _kb_raise_or_return(self, response: Any) -> dict[str, Any] | list[Any]:
        """Raise ZammadAPIError on HTTP error, otherwise return the parsed JSON body.

        Empty, malformed, or unexpected bodies on KB endpoints are also raised
        as ZammadAPIError so API failures never leak untyped exceptions.
        """
        if not _is_2xx(response.status_code):
            try:
                body = response.json()
            except ValueError:
                body = response.text
            raise ZammadAPIError(response.status_code, response.url, body)
        if response.status_code == _HTTP_NO_CONTENT or not response.content:
            raise ZammadAPIError(
                response.status_code,
                response.url,
                "Empty response body from KB endpoint",
            )
        try:
            data = response.json()
        except (TypeError, ValueError) as exc:
            raise ZammadAPIError(response.status_code, response.url, response.text) from exc
        if isinstance(data, (dict, list)):
            return data
        raise ZammadAPIError(
            response.status_code,
            response.url,
            f"Unexpected KB response shape: {type(data).__name__}",
        )

    def list_knowledge_bases(self) -> list[dict[str, Any]]:
        """List all knowledge bases from Zammad's permission-filtered bootstrap payload."""
        response = self.api.session.post(self.api.url + "knowledge_bases/init")
        payload = self._kb_raise_or_return(response)
        if not isinstance(payload, dict):
            raise ZammadAPIError(
                response.status_code,
                response.url,
                f"Unexpected knowledge_bases init response shape: {type(payload).__name__}",
            )
        assets = payload.get("assets", {})
        if not isinstance(assets, dict):
            raise ZammadAPIError(
                response.status_code,
                response.url,
                f"Unexpected knowledge_bases assets shape: {type(assets).__name__}",
            )
        knowledge_bases = assets.get("KnowledgeBase", {})
        if not isinstance(knowledge_bases, dict):
            raise ZammadAPIError(
                response.status_code,
                response.url,
                f"Unexpected KnowledgeBase assets shape: {type(knowledge_bases).__name__}",
            )
        results: list[dict[str, Any]] = []
        for knowledge_base in knowledge_bases.values():
            if not isinstance(knowledge_base, dict) or not knowledge_base:
                raise ZammadAPIError(
                    response.status_code,
                    response.url,
                    f"Unexpected KnowledgeBase asset shape: {type(knowledge_base).__name__}",
                )
            results.append(knowledge_base)
        return results

    def get_knowledge_base(self, kb_id: int) -> dict[str, Any]:
        """Get a single knowledge base by ID."""
        response = self.api.session.get(self._kb_url(kb_id))
        result = self._kb_raise_or_return(response)
        if not isinstance(result, dict):
            raise ZammadAPIError(
                response.status_code,
                response.url,
                f"Unexpected knowledge_base response shape: {type(result).__name__}",
            )
        return result

    def get_kb_category(self, kb_id: int, category_id: int) -> dict[str, Any]:
        """Get a single KB category."""
        response = self.api.session.get(self._kb_url(kb_id, "categories", category_id))
        result = self._kb_raise_or_return(response)
        if not isinstance(result, dict):
            raise ZammadAPIError(
                response.status_code,
                response.url,
                f"Unexpected kb_category response shape: {type(result).__name__}",
            )
        return result

    def get_kb_answer(self, kb_id: int, answer_id: int) -> dict[str, Any]:
        """
        Get a single KB answer including translation/body content.

        Fetches the answer and re-fetches with ?include_contents={translation_id}
        so KnowledgeBaseAnswerTranslationContent (body) is included.
        """
        url = self._kb_url(kb_id, "answers", answer_id)
        response = self.api.session.get(url)
        payload = self._kb_raise_or_return(response)
        if not isinstance(payload, dict):
            raise ZammadAPIError(
                response.status_code,
                response.url,
                f"Unexpected kb_answer response shape: {type(payload).__name__}",
            )
        assets = payload.get("assets") or {}
        answer_entry = (assets.get("KnowledgeBaseAnswer") or {}).get(str(answer_id)) or {}
        translation_ids: list[int] = answer_entry.get("translation_ids") or []
        if translation_ids:
            translation_id = translation_ids[0]
            response2 = self.api.session.get(url, params={"include_contents": translation_id})
            data = self._kb_raise_or_return(response2)
            if isinstance(data, dict):
                return data
        return payload

    # --- KB extraction helpers (operate on compound payloads) ---

    def _first_translation_field(
        self,
        translations: dict[str, Any],
        translation_ids: list[int],
        field: str,
    ) -> str:
        """Return the first non-empty string field from translations."""
        for tid in translation_ids:
            value = (translations.get(str(tid)) or {}).get(field)
            if value:
                return str(value)
        first: dict[str, Any] = next(iter(translations.values()), {})
        return str(first[field]) if first.get(field) else ""

    def _extract_kb_answer_title(self, raw_payload: dict[str, Any], answer: dict[str, Any]) -> str:
        """Extract the first available title from translation assets."""
        assets = raw_payload.get("assets") or {}
        translations = assets.get("KnowledgeBaseAnswerTranslation") or {}
        if not translations:
            return ""
        translation_ids: list[int] = answer.get("translation_ids") or []
        return self._first_translation_field(translations, translation_ids, "title")

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags and unescape entities from a string."""
        return _html.unescape(_re.sub(r"<[^>]+>", " ", html))

    def _body_from_content_assets(self, contents: dict[str, Any], translation_ids: list[int]) -> str:
        """Extract plain-text body from KnowledgeBaseAnswerTranslationContent."""
        for tid in translation_ids:
            body = (contents.get(str(tid)) or {}).get("body") or ""
            if body:
                return self._strip_html(body)
        first: dict[str, Any] = next(iter(contents.values()), {})
        first_body = first.get("body") or ""
        return self._strip_html(first_body) if first_body else ""

    def _body_from_translation_assets(self, translations: dict[str, Any], translation_ids: list[int]) -> str:
        """Extract plain-text body from translation content_attributes (legacy).

        Translations named by ``translation_ids`` are preferred, in order; any other
        translation with a body is the fallback when those ids are stale.
        """
        preferred = [translations.get(str(tid)) for tid in translation_ids]
        candidates = [*preferred, *translations.values()]
        bodies = (((t or {}).get("content_attributes") or {}).get("body") or "" for t in candidates)
        body = next((b for b in bodies if b), "")
        return self._strip_html(body) if body else ""

    def _extract_kb_answer_body(self, raw_payload: dict[str, Any], answer: dict[str, Any]) -> str:
        """Extract the plain-text body from translation assets."""
        assets = raw_payload.get("assets") or {}
        translation_ids: list[int] = answer.get("translation_ids") or []
        contents = assets.get("KnowledgeBaseAnswerTranslationContent") or {}
        if contents:
            return self._body_from_content_assets(contents, translation_ids)
        translations = assets.get("KnowledgeBaseAnswerTranslation") or {}
        if translations:
            return self._body_from_translation_assets(translations, translation_ids)
        return ""

    def _extract_kb_answer_from_payload(self, payload: dict[str, Any], answer_id: int) -> dict[str, Any] | None:
        """Extract the answer dict from a compound KB answer payload."""
        assets = payload.get("assets") or {}
        kb_answers = assets.get("KnowledgeBaseAnswer")
        if kb_answers:
            return kb_answers.get(str(answer_id)) or next(iter(kb_answers.values()), None)
        if "KnowledgeBaseAnswer" in payload:
            answers_map = payload["KnowledgeBaseAnswer"]
            return answers_map.get(str(answer_id)) or next(iter(answers_map.values()), None)
        return payload if payload else None

    def get_kb_answer_with_content(self, kb_id: int, answer_id: int) -> dict[str, Any]:
        """
        Get a KB answer with extracted title and body as a single processed dict.

        The returned dict has the keys ``answer`` (flat answer dict),
        ``title`` (str) and ``body`` (str, plain text with HTML stripped).
        """
        payload = self.get_kb_answer(kb_id, answer_id)
        answer = self._extract_kb_answer_from_payload(payload, answer_id) or payload
        return {
            "answer": answer,
            "title": self._extract_kb_answer_title(payload, answer),
            "body": self._extract_kb_answer_body(payload, answer),
        }

    def list_kb_answers(self, kb_id: int, category_id: int) -> list[dict[str, Any]]:
        """
        List answers within a KB category by expanding the category's answer_ids.

        Each returned answer has '_title' and '_body' injected from translation
        assets. Per-answer 404s are tolerated as a documented compatibility
        path (an answer ID listed by the category may have been deleted in a
        race); all other errors are surfaced as :class:`ZammadAPIError`.
        """
        category = self.get_kb_category(kb_id, category_id)
        answer_ids: list[int] = category.get("answer_ids") or []
        answers: list[dict[str, Any]] = []
        for aid in answer_ids:
            try:
                answer_data = self.get_kb_answer(kb_id, aid)
            except ZammadAPIError as exc:
                if exc.status_code == _HTTP_NOT_FOUND:
                    logger.warning("KB answer %d not found in category %d", aid, category_id)
                    continue
                raise
            answer_entry = self._extract_kb_answer_from_payload(answer_data, aid)
            if answer_entry is None:
                logger.warning("Failed to parse KB answer %d in category %d", aid, category_id)
                continue
            answer_entry["_title"] = self._extract_kb_answer_title(answer_data, answer_entry)
            answer_entry["_body"] = self._extract_kb_answer_body(answer_data, answer_entry)
            answers.append(answer_entry)
        return answers

    def _answer_matches_query(self, answer: dict[str, Any], query_lower: str) -> bool:
        """Return True if query_lower appears in the answer's title or body."""
        title = answer.get("_title") or ""
        body = answer.get("_body") or ""
        return query_lower in title.lower() or query_lower in body.lower()

    def _collect_category_answers(self, kb_id: int, cid: int, query_lower: str) -> list[dict[str, Any]]:
        """
        Return matching answers from a single category.

        Tolerates 404 on the category lookup (documented compatibility path);
        all other errors are surfaced as :class:`ZammadAPIError`.
        """
        matches: list[dict[str, Any]] = []
        try:
            answers = self.list_kb_answers(kb_id, cid)
        except ZammadAPIError as exc:
            if exc.status_code == _HTTP_NOT_FOUND:
                logger.warning("KB category %d not found during search", cid)
                return matches
            raise
        for answer in answers:
            if self._answer_matches_query(answer, query_lower):
                answer["_category_id"] = cid
                matches.append(answer)
        return matches

    def _answers_matching_query(self, kb_id: int, category_ids: list[int], query_lower: str) -> list[dict[str, Any]]:
        """Return answers whose title or body matches query_lower."""
        results: list[dict[str, Any]] = []
        for cid in category_ids:
            results.extend(self._collect_category_answers(kb_id, cid, query_lower))
        return results

    def _expand_category_ids(self, kb_id: int, root_ids: list[int]) -> list[int]:
        """BFS-expand root category IDs into all descendants via child_ids."""
        visited: list[int] = []
        queue = deque(root_ids)
        seen: set[int] = set()
        while queue:
            cid = queue.popleft()
            if cid in seen:
                continue
            seen.add(cid)
            visited.append(cid)
            try:
                category = self.get_kb_category(kb_id, cid)
            except ZammadAPIError as exc:
                if exc.status_code == _HTTP_NOT_FOUND:
                    logger.warning("KB category %d not found while expanding tree", cid)
                    continue
                raise
            for child_id in category.get("child_ids") or []:
                if child_id not in seen:
                    queue.append(child_id)
        return visited

    def search_kb_answers(self, kb_id: int, query: str, category_id: int | None = None) -> list[dict[str, Any]]:
        """
        Case-insensitive substring search of KB answers across categories.

        If ``category_id`` is provided, search is limited to that category and
        its descendants. Otherwise all root categories of the KB are scanned.
        """
        kb = self.get_knowledge_base(kb_id)
        root_ids = [category_id] if category_id is not None else (kb.get("category_ids") or [])
        category_ids = self._expand_category_ids(kb_id, root_ids)
        return self._answers_matching_query(kb_id, category_ids, query.lower())

    def merge_tickets(
        self,
        source_ticket_id: int,
        target_ticket_number: str | None = None,
        target_ticket_id: int | None = None,
    ) -> dict[str, Any]:
        """Merge a source ticket into a target ticket via the legacy ticket_merge endpoint.

        The endpoint identifies the source by internal ID and the target by
        display number, so a target given by ID is resolved to its number first.

        Args:
            source_ticket_id: Internal ID of the ticket that will be merged away.
            target_ticket_number: Optional. Display number of the surviving ticket.
            target_ticket_id: Optional. Internal ID of the surviving ticket.

        Returns:
            Raw merge response with ``result`` and ``target_ticket`` keys.

        Raises:
            ValueError: If not exactly one target is given, or Zammad reports failure in-band.
            requests.HTTPError: If the API request fails (e.g., 403 Forbidden, 404 Not Found).

        """
        if (target_ticket_number is None) == (target_ticket_id is None):
            msg = "Provide exactly one of target_ticket_number or target_ticket_id"
            raise ValueError(msg)
        if target_ticket_number is None:
            target_ticket_number = str(self.api.ticket.find(target_ticket_id)["number"])

        # Encode as a single path segment so "/" or "?" in a caller-supplied number
        # cannot redirect the authenticated PUT to a different endpoint.
        target_segment = quote(target_ticket_number, safe="")
        response = self.api.session.put(f"{self.url}/ticket_merge/{source_ticket_id}/{target_segment}")
        response.raise_for_status()
        payload = dict(response.json())
        if payload.get("result") != "success":
            msg = f"Zammad refused to merge ticket {source_ticket_id} into #{target_ticket_number}: {payload.get('message', payload)}"
            raise ValueError(msg)
        return payload
