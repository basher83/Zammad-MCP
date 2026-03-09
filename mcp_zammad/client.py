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
        attachments: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Add an article (comment/note) to a ticket with optional attachments.

        Args:
            ticket_id: Ticket ID to add article to
            body: Article body content
            article_type: Article type (note, email, phone)
            internal: Whether the article is internal
            sender: Sender type (Agent, Customer, System)
            attachments: Optional list of attachments with keys:
                - filename: str
                - data: str (base64-encoded content)
                - mime-type: str

        Returns:
            Created article data with attachment metadata
        """
        article_data = {
            "ticket_id": ticket_id,
            "body": body,
            "type": article_type,
            "internal": internal,
            "sender": sender,
        }

        if attachments:
            article_data["attachments"] = attachments

        return dict(self.api.ticket_article.create(article_data))

    def delete_attachment(self, ticket_id: int, article_id: int, attachment_id: int) -> bool:
        """Delete an attachment from a ticket article.

        Args:
            ticket_id: Ticket ID
            article_id: Article ID
            attachment_id: Attachment ID to delete

        Returns:
            True if deletion succeeded

        Raises:
            Exception if deletion fails
        """
        result = self.api.ticket_article_attachment.destroy(attachment_id, article_id, ticket_id)
        # destroy() returns True on success, may return dict on error
        return bool(result)

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

    # ------------------------------------------------------------------
    # Knowledge Base methods (direct HTTP – not covered by zammad_py)
    # ------------------------------------------------------------------

    def _kb_url(self, *parts: str | int) -> str:
        """Build a knowledge-base API URL from path components.

        Args:
            *parts: URL path segments joined with '/'

        Returns:
            Full API URL string
        """
        path = "/".join(str(p) for p in parts)
        return f"{self.api.url}knowledge_bases/{path}"

    def _kb_raise_or_return(self, response: Any) -> dict[str, Any] | list[Any]:
        """Raise on HTTP error; return parsed JSON body.

        Args:
            response: requests.Response object

        Returns:
            Parsed JSON (dict or list)

        Raises:
            Exception: if HTTP status is 4xx/5xx
        """
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        data = response.json()
        if isinstance(data, list):
            return data
        return dict(data)

    def list_knowledge_bases(self) -> list[dict[str, Any]]:
        """List all knowledge bases.

        Returns:
            List of knowledge base dicts
        """
        response = self.api.session.get(self.api.url + "knowledge_bases")
        data = self._kb_raise_or_return(response)
        if isinstance(data, list):
            return list(data)
        return [data] if data else []

    def get_knowledge_base(self, kb_id: int) -> dict[str, Any]:
        """Get a single knowledge base by ID.

        Args:
            kb_id: Knowledge base ID

        Returns:
            Knowledge base dict
        """
        response = self.api.session.get(self._kb_url(kb_id))
        return self._kb_raise_or_return(response)

    def get_kb_category(self, kb_id: int, category_id: int) -> dict[str, Any]:
        """Get a single KB category.

        Args:
            kb_id: Knowledge base ID
            category_id: Category ID

        Returns:
            Category dict
        """
        response = self.api.session.get(self._kb_url(kb_id, "categories", category_id))
        return self._kb_raise_or_return(response)

    def create_kb_category(
        self,
        kb_id: int,
        title: str,
        kb_locale_id: int,
        parent_id: int | None = None,
        category_icon: str | None = None,
    ) -> dict[str, Any]:
        """Create a new KB category.

        Args:
            kb_id: Knowledge base ID
            title: Category title (for the given locale)
            kb_locale_id: KB locale ID to attach the title translation to
            parent_id: Optional parent category ID
            category_icon: Optional FontAwesome icon code

        Returns:
            Created category dict
        """
        payload: dict[str, Any] = {
            "translations_attributes": [{"title": title, "kb_locale_id": kb_locale_id}],
        }
        if parent_id is not None:
            payload["parent_id"] = parent_id
        if category_icon is not None:
            payload["category_icon"] = category_icon
        response = self.api.session.post(self._kb_url(kb_id, "categories"), json=payload)
        return self._kb_raise_or_return(response)

    def update_kb_category(
        self,
        kb_id: int,
        category_id: int,
        title: str | None = None,
        translation_id: int | None = None,
        parent_id: int | None = None,
        category_icon: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing KB category.

        Args:
            kb_id: Knowledge base ID
            category_id: Category ID
            title: New title for the category translation
            translation_id: Translation ID to update (required when title is provided)
            parent_id: New parent category ID
            category_icon: New FontAwesome icon code

        Returns:
            Updated category dict
        """
        payload: dict[str, Any] = {}
        if title is not None:
            translation_entry: dict[str, Any] = {"title": title}
            if translation_id is not None:
                translation_entry["id"] = translation_id
            payload["translations_attributes"] = [translation_entry]
        if parent_id is not None:
            payload["parent_id"] = parent_id
        if category_icon is not None:
            payload["category_icon"] = category_icon
        response = self.api.session.patch(
            self._kb_url(kb_id, "categories", category_id), json=payload
        )
        return self._kb_raise_or_return(response)

    def delete_kb_category(self, kb_id: int, category_id: int) -> dict[str, Any]:
        """Delete a KB category.

        Args:
            kb_id: Knowledge base ID
            category_id: Category ID

        Returns:
            Empty dict on success
        """
        response = self.api.session.delete(self._kb_url(kb_id, "categories", category_id))
        return self._kb_raise_or_return(response)

    def get_kb_answer(self, kb_id: int, answer_id: int) -> dict[str, Any]:
        """Get a single KB answer.

        Args:
            kb_id: Knowledge base ID
            answer_id: Answer ID

        Returns:
            Answer dict (compound payload including translations/attachments)
        """
        response = self.api.session.get(self._kb_url(kb_id, "answers", answer_id))
        return self._kb_raise_or_return(response)

    def list_kb_answers(self, kb_id: int, category_id: int) -> list[dict[str, Any]]:
        """List answers in a KB category by fetching the category and expanding answer IDs.

        Args:
            kb_id: Knowledge base ID
            category_id: Category ID

        Returns:
            List of answer dicts
        """
        category = self.get_kb_category(kb_id, category_id)
        answer_ids: list[int] = category.get("answer_ids") or []
        answers = []
        for aid in answer_ids:
            try:
                answer_data = self.get_kb_answer(kb_id, aid)
                answer_entry = self._extract_kb_answer_from_payload(answer_data, aid)
                if answer_entry:
                    answers.append(answer_entry)
            except Exception:
                logger.warning("Failed to fetch KB answer %d in category %d", aid, category_id)
        return answers

    def _extract_kb_answer_from_payload(self, payload: dict[str, Any], answer_id: int) -> dict[str, Any] | None:
        """Extract the answer dict from a compound KB answer payload.

        Zammad's KB answer endpoint may return a compound payload keyed by
        'KnowledgeBaseAnswer'. If so, extract the entry for answer_id.

        Args:
            payload: Raw API response dict
            answer_id: The answer ID to extract

        Returns:
            Answer dict or None
        """
        if "KnowledgeBaseAnswer" in payload:
            answers_map = payload["KnowledgeBaseAnswer"]
            return answers_map.get(str(answer_id)) or next(iter(answers_map.values()), None)
        return payload if payload else None

    def create_kb_answer(
        self,
        kb_id: int,
        category_id: int,
        title: str,
        body: str,
        kb_locale_id: int,
    ) -> dict[str, Any]:
        """Create a new KB answer.

        Args:
            kb_id: Knowledge base ID
            category_id: Category ID
            title: Answer title
            body: Answer body (HTML or plain text)
            kb_locale_id: KB locale ID

        Returns:
            Created answer dict (compound payload)
        """
        payload: dict[str, Any] = {
            "category_id": category_id,
            "translations_attributes": [
                {
                    "title": title,
                    "kb_locale_id": kb_locale_id,
                    "content_attributes": {"body": body},
                }
            ],
        }
        response = self.api.session.post(self._kb_url(kb_id, "answers"), json=payload)
        return self._kb_raise_or_return(response)

    def update_kb_answer(
        self,
        kb_id: int,
        answer_id: int,
        title: str | None = None,
        translation_id: int | None = None,
        body: str | None = None,
        category_id: int | None = None,
    ) -> dict[str, Any]:
        """Update an existing KB answer.

        Args:
            kb_id: Knowledge base ID
            answer_id: Answer ID
            title: New title
            translation_id: Translation ID (required when updating title/body)
            body: New body content
            category_id: Move answer to a different category

        Returns:
            Updated answer dict (compound payload)
        """
        payload: dict[str, Any] = {}
        if title is not None or body is not None:
            translation_entry: dict[str, Any] = {}
            if translation_id is not None:
                translation_entry["id"] = translation_id
            if title is not None:
                translation_entry["title"] = title
            if body is not None:
                translation_entry["content_attributes"] = {"body": body}
            payload["translations_attributes"] = [translation_entry]
        if category_id is not None:
            payload["category_id"] = category_id
        response = self.api.session.patch(
            self._kb_url(kb_id, "answers", answer_id), json=payload
        )
        return self._kb_raise_or_return(response)

    def delete_kb_answer(self, kb_id: int, answer_id: int) -> dict[str, Any]:
        """Delete a KB answer.

        Args:
            kb_id: Knowledge base ID
            answer_id: Answer ID

        Returns:
            Empty dict on success
        """
        response = self.api.session.delete(self._kb_url(kb_id, "answers", answer_id))
        return self._kb_raise_or_return(response)

    def publish_kb_answer(self, kb_id: int, answer_id: int) -> dict[str, Any]:
        """Publish a KB answer publicly.

        Args:
            kb_id: Knowledge base ID
            answer_id: Answer ID

        Returns:
            Updated answer dict (compound payload)
        """
        response = self.api.session.post(self._kb_url(kb_id, "answers", answer_id, "publish"))
        return self._kb_raise_or_return(response)

    def internalize_kb_answer(self, kb_id: int, answer_id: int) -> dict[str, Any]:
        """Publish a KB answer for internal use only.

        Args:
            kb_id: Knowledge base ID
            answer_id: Answer ID

        Returns:
            Updated answer dict (compound payload)
        """
        response = self.api.session.post(self._kb_url(kb_id, "answers", answer_id, "internal"))
        return self._kb_raise_or_return(response)

    def archive_kb_answer(self, kb_id: int, answer_id: int) -> dict[str, Any]:
        """Archive a KB answer.

        Args:
            kb_id: Knowledge base ID
            answer_id: Answer ID

        Returns:
            Updated answer dict (compound payload)
        """
        response = self.api.session.post(self._kb_url(kb_id, "answers", answer_id, "archive"))
        return self._kb_raise_or_return(response)

    def unarchive_kb_answer(self, kb_id: int, answer_id: int) -> dict[str, Any]:
        """Unarchive a KB answer.

        Args:
            kb_id: Knowledge base ID
            answer_id: Answer ID

        Returns:
            Updated answer dict (compound payload)
        """
        response = self.api.session.post(self._kb_url(kb_id, "answers", answer_id, "unarchive"))
        return self._kb_raise_or_return(response)

    def add_kb_answer_attachment(
        self, kb_id: int, answer_id: int, filename: str, data: str, mime_type: str
    ) -> dict[str, Any]:
        """Add a base64-encoded attachment to a KB answer.

        Args:
            kb_id: Knowledge base ID
            answer_id: Answer ID
            filename: Attachment filename
            data: Base64-encoded file content
            mime_type: MIME type of the attachment

        Returns:
            Updated answer dict (compound payload)
        """
        payload = {
            "attachments": [
                {
                    "filename": filename,
                    "data": data,
                    "mime-type": mime_type,
                }
            ]
        }
        response = self.api.session.post(
            self._kb_url(kb_id, "answers", answer_id, "attachments"), json=payload
        )
        return self._kb_raise_or_return(response)

    def delete_kb_answer_attachment(
        self, kb_id: int, answer_id: int, attachment_id: int
    ) -> dict[str, Any]:
        """Delete an attachment from a KB answer.

        Args:
            kb_id: Knowledge base ID
            answer_id: Answer ID
            attachment_id: Attachment ID to delete

        Returns:
            Empty dict on success
        """
        response = self.api.session.delete(
            self._kb_url(kb_id, "answers", answer_id, "attachments", attachment_id)
        )
        return self._kb_raise_or_return(response)
