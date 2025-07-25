"""Zammad API client wrapper for the MCP server."""

import logging
import os
from typing import Any
from urllib.parse import urlparse

from zammad_py import ZammadAPI
from zammad_py.exceptions import ConfigException

logger = logging.getLogger(__name__)


class ZammadClient:
    """Wrapper around zammad_py ZammadAPI with additional functionality."""

    def __init__(
        self,
        url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        http_token: str | None = None,
        oauth2_token: str | None = None,
    ):
        """Initialize Zammad client with environment variables or provided credentials.

        Supports reading secrets from files using Docker secrets pattern:
        - ZAMMAD_HTTP_TOKEN_FILE: Path to file containing HTTP token
        - ZAMMAD_OAUTH2_TOKEN_FILE: Path to file containing OAuth2 token
        - ZAMMAD_PASSWORD_FILE: Path to file containing password
        """
        self.url = url or os.getenv("ZAMMAD_URL")
        self.username = username or os.getenv("ZAMMAD_USERNAME")

        # Try to read secrets from files first (Docker secrets pattern)
        self.password = password or self._read_secret_file("ZAMMAD_PASSWORD_FILE") or os.getenv("ZAMMAD_PASSWORD")
        self.http_token = (
            http_token or self._read_secret_file("ZAMMAD_HTTP_TOKEN_FILE") or os.getenv("ZAMMAD_HTTP_TOKEN")
        )
        self.oauth2_token = (
            oauth2_token or self._read_secret_file("ZAMMAD_OAUTH2_TOKEN_FILE") or os.getenv("ZAMMAD_OAUTH2_TOKEN")
        )

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

            # Block local/private networks (optional - adjust based on your security requirements)
            hostname = parsed.hostname.lower() if parsed.hostname else ""
            blocked_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "::1"]  # nosec B104
            if hostname in blocked_hosts:
                logger.warning(f"Zammad URL points to local host: {hostname}")

            # Check for private IP ranges (optional)
            if hostname.startswith(("10.", "192.168.", "172.")):
                logger.warning(f"Zammad URL points to private network: {hostname}")

        except Exception as e:
            raise ConfigException(f"Invalid Zammad URL format: {e}") from e

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

    def search_tickets(
        self,
        query: str | None = None,
        state: str | None = None,
        priority: str | None = None,
        group: str | None = None,
        owner: str | None = None,
        customer: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> list[dict[str, Any]]:
        """Search tickets with various filters."""
        filters = {"page": page, "per_page": per_page, "expand": True}

        # Build search query
        search_parts = []
        if query:
            search_parts.append(query)
        if state:
            search_parts.append(f"state.name:{state}")
        if priority:
            search_parts.append(f"priority.name:{priority}")
        if group:
            search_parts.append(f"group.name:{group}")
        if owner:
            search_parts.append(f"owner.login:{owner}")
        if customer:
            search_parts.append(f"customer.email:{customer}")

        if search_parts:
            search_query = " AND ".join(search_parts)
            result = self.api.ticket.search(search_query, filters=filters)
        else:
            result = self.api.ticket.all(filters=filters)

        return list(result)

    def get_ticket(
        self, ticket_id: int, include_articles: bool = True, article_limit: int = 10, article_offset: int = 0
    ) -> dict[str, Any]:
        """Get a single ticket by ID with optional article pagination."""
        ticket = self.api.ticket.find(ticket_id)

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
    ) -> dict[str, Any]:
        """Update an existing ticket."""
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if state is not None:
            update_data["state"] = state
        if priority is not None:
            update_data["priority"] = priority
        if owner is not None:
            update_data["owner"] = owner
        if group is not None:
            update_data["group"] = group

        return dict(self.api.ticket.update(ticket_id, update_data))

    def add_article(
        self,
        ticket_id: int,
        body: str,
        article_type: str = "note",
        internal: bool = False,
        sender: str = "Agent",
    ) -> dict[str, Any]:
        """Add an article (comment/note) to a ticket."""
        article_data = {
            "ticket_id": ticket_id,
            "body": body,
            "type": article_type,
            "internal": internal,
            "sender": sender,
        }

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
        filters = {"page": page, "per_page": per_page, "expand": True}
        result = self.api.user.search(query, filters=filters)
        return list(result)

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
        filters = {"page": page, "per_page": per_page, "expand": True}
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
        """Add a tag to a ticket."""
        return dict(self.api.ticket_tag.add(ticket_id, tag))

    def remove_ticket_tag(self, ticket_id: int, tag: str) -> dict[str, Any]:
        """Remove a tag from a ticket."""
        return dict(self.api.ticket_tag.remove(ticket_id, tag))

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
