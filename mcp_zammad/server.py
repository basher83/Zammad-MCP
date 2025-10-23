"""Zammad MCP Server implementation."""

import base64
import html
import json
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Protocol, TypeVar

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from .client import ZammadClient
from .models import (
    Article,
    ArticleCreate,
    Attachment,
    AttachmentDownloadError,
    DownloadAttachmentParams,
    GetArticleAttachmentsParams,
    GetOrganizationParams,
    GetTicketParams,
    GetTicketStatsParams,
    GetUserParams,
    Group,
    ListParams,
    Organization,
    PriorityBrief,
    ResponseFormat,
    SearchOrganizationsParams,
    SearchUsersParams,
    StateBrief,
    TagOperationParams,
    TagOperationResult,
    Ticket,
    TicketCreate,
    TicketIdGuidanceError,
    TicketPriority,
    TicketSearchParams,
    TicketState,
    TicketStats,
    TicketUpdateParams,
    User,
    UserBrief,
)


# Protocol for items that can be dumped to dict (for type safety)
class _Dumpable(Protocol):
    """Protocol for Pydantic models with id, name, and model_dump."""

    id: int
    name: str

    def model_dump(self) -> dict[str, Any]: ...


T = TypeVar("T", bound=_Dumpable)

# Configure logging
logger = logging.getLogger(__name__)

# Constants
MAX_PAGES_FOR_TICKET_SCAN = 1000
MAX_TICKETS_PER_STATE_IN_QUEUE = 10
MAX_PER_PAGE = 100  # Maximum results per page for pagination
CHARACTER_LIMIT = int(os.getenv("ZAMMAD_MCP_CHARACTER_LIMIT", "25000"))  # Maximum response size in characters

# Zammad state type IDs (from Zammad API)
STATE_TYPE_NEW = 1
STATE_TYPE_OPEN = 2
STATE_TYPE_CLOSED = 3
STATE_TYPE_PENDING_REMINDER = 4
STATE_TYPE_PENDING_CLOSE = 5


def _brief_field(value: Any, attr: str) -> str:
    """Extract a field from a Brief model or return Unknown.

    Handles StateBrief, PriorityBrief, UserBrief objects or string fallbacks.

    Args:
        value: The value to extract from (Brief model, string, or None)
        attr: The attribute name to extract

    Returns:
        The extracted value or "Unknown"
    """
    if isinstance(value, (StateBrief, PriorityBrief, UserBrief)):  # noqa: UP038
        v = getattr(value, attr, None)
        return v or "Unknown"
    if isinstance(value, str):
        return value
    return "Unknown"


def _escape_article_body(article: Article) -> str:
    """Escape HTML in article bodies to prevent injection.

    Args:
        article: The article to get the body from

    Returns:
        HTML-escaped body if content type is HTML, otherwise raw body
    """
    ct = (getattr(article, "content_type", None) or "").lower()
    return html.escape(article.body) if "html" in ct else article.body


def _serialize_json(obj: dict[str, Any], use_compact: bool) -> str:
    """Serialize JSON object with appropriate formatting.

    Args:
        obj: Dictionary to serialize
        use_compact: If True, use compact format; otherwise use indented format

    Returns:
        JSON string
    """
    if use_compact:
        return json.dumps(obj, separators=(",", ":"), default=str)
    return json.dumps(obj, indent=2, default=str)


def _find_max_items_for_limit(obj: dict[str, Any], original_items: list[Any], limit: int, use_compact: bool) -> int:
    """Binary search to find max items that fit under limit.

    Args:
        obj: JSON object to truncate
        original_items: Original items array
        limit: Character limit
        use_compact: Whether to use compact JSON format

    Returns:
        Maximum number of items that fit
    """
    left, right = 0, len(original_items)
    while left < right:
        mid = (left + right + 1) // 2
        obj["items"] = original_items[:mid]
        if len(_serialize_json(obj, use_compact)) <= limit:
            left = mid
        else:
            right = mid - 1
    return left


def _truncate_json_response(content: str, obj: dict[str, Any], limit: int) -> str:
    """Truncate JSON response preserving validity.

    Args:
        content: Original content string
        obj: Parsed JSON object
        limit: Character limit

    Returns:
        Truncated JSON string
    """
    original_size = len(content)
    use_compact = original_size > limit * 1.2

    # Attempt to shrink the "items" array if present
    if "items" in obj and isinstance(obj["items"], list):
        original_items = obj["items"]
        max_items = _find_max_items_for_limit(obj, original_items, limit, use_compact)
        obj["items"] = original_items[:max_items]

    # Add metadata about truncation
    meta = obj.setdefault("_meta", {})
    meta.update(
        {
            "truncated": True,
            "original_size": original_size,
            "limit": limit,
            "note": "Response truncated; reduce page/per_page or add filters.",
        }
    )

    # Ensure final JSON (including metadata) fits under limit
    if "items" in obj and isinstance(obj["items"], list):
        json_str = _serialize_json(obj, use_compact)
        while obj["items"] and len(json_str) > limit:
            obj["items"].pop()
            json_str = _serialize_json(obj, use_compact)

    return _serialize_json(obj, use_compact)


def _truncate_text_response(content: str, limit: int) -> str:
    """Truncate plaintext/markdown response with warning.

    Args:
        content: Original content
        limit: Character limit

    Returns:
        Truncated content with warning message
    """
    truncated = content[:limit]
    truncated += "\n\n⚠️ **Response Truncated**\n"
    truncated += f"Response size ({len(content)} chars) exceeds limit ({limit} chars).\n"
    truncated += "Use pagination (page/per_page) or add filters to see more results."
    return truncated


def truncate_response(content: str, limit: int = CHARACTER_LIMIT) -> str:
    """Truncate response with helpful message if over limit.

    For JSON responses, preserves validity by shrinking arrays and adding metadata.
    For markdown/text responses, appends a truncation warning.

    Args:
        content: The content to potentially truncate
        limit: Maximum character limit (default: CHARACTER_LIMIT)

    Returns:
        Original content if under limit, truncated content with warning if over
    """
    if len(content) <= limit:
        return content

    # Try to preserve JSON validity if the content is JSON
    if content.lstrip().startswith("{"):
        try:
            obj = json.loads(content)
            return _truncate_json_response(content, obj, limit)
        except Exception as e:
            # fall back to plaintext truncation if JSON parsing fails
            logger.debug("Failed to parse/truncate JSON response: %s", e, exc_info=True)

    # Plaintext/Markdown truncation
    return _truncate_text_response(content, limit)


def _format_tickets_markdown(tickets: list[Ticket], query_info: str = "Search Results") -> str:
    """Format tickets as markdown for human readability.

    Args:
        tickets: List of tickets to format
        query_info: Description of the query/search

    Returns:
        Markdown-formatted string
    """
    lines = [f"# Ticket Search Results: {query_info}", ""]
    lines.append(f"Found {len(tickets)} ticket(s)")
    lines.append("")

    for ticket in tickets:
        # Handle expanded fields with safe fallback
        if isinstance(ticket.state, StateBrief):
            state_name = ticket.state.name
        elif isinstance(ticket.state, str):
            state_name = ticket.state
        else:
            state_name = "Unknown"
        if isinstance(ticket.priority, PriorityBrief):
            priority_name = ticket.priority.name
        elif isinstance(ticket.priority, str):
            priority_name = ticket.priority
        else:
            priority_name = "Unknown"

        lines.append(f"## Ticket #{ticket.number} - {ticket.title}")
        lines.append(f"- **ID**: {ticket.id}")
        lines.append(f"- **State**: {state_name}")
        lines.append(f"- **Priority**: {priority_name}")
        # Use isoformat() to include timezone information if available
        lines.append(f"- **Created**: {ticket.created_at.isoformat()}")
        lines.append("")

    return "\n".join(lines)


def _format_tickets_json(tickets: list[Ticket], total: int | None, page: int, per_page: int) -> str:
    """Format tickets as JSON for programmatic processing.

    Args:
        tickets: List of tickets to format
        total: Total count of matching tickets across all pages (None if unknown)
        page: Current page number
        per_page: Results per page

    Returns:
        JSON-formatted string with pagination metadata
    """
    response: dict[str, Any] = {
        "items": [ticket.model_dump() for ticket in tickets],
        "total": total,  # None when true total is unknown
        "count": len(tickets),
        "page": page,
        "per_page": per_page,
        "offset": (page - 1) * per_page,
        "has_more": len(tickets) == per_page,  # heuristic when total unknown
        "next_page": page + 1 if len(tickets) == per_page else None,
        "next_offset": page * per_page if len(tickets) == per_page else None,
        "_meta": {},  # Pre-allocated for truncation flags
    }

    return json.dumps(response, indent=2, default=str)


def _format_users_markdown(users: list[User], query_info: str = "Search Results") -> str:
    """Format users as markdown for human readability.

    Args:
        users: List of users to format
        query_info: Description of the query/search

    Returns:
        Markdown-formatted string
    """
    lines = [f"# User Search Results: {query_info}", ""]
    lines.append(f"Found {len(users)} user(s)")
    lines.append("")

    for user in users:
        full_name = f"{user.firstname or ''} {user.lastname or ''}".strip() or "N/A"
        lines.append(f"## {full_name}")
        lines.append(f"- **ID**: {user.id}")
        lines.append(f"- **Email**: {user.email or 'N/A'}")
        lines.append(f"- **Login**: {user.login or 'N/A'}")
        lines.append(f"- **Active**: {user.active}")
        lines.append("")

    return "\n".join(lines)


def _format_users_json(users: list[User], total: int | None, page: int, per_page: int) -> str:
    """Format users as JSON for programmatic processing.

    Args:
        users: List of users to format
        total: Total count of matching users across all pages (None if unknown)
        page: Current page number
        per_page: Results per page

    Returns:
        JSON-formatted string with pagination metadata
    """
    response: dict[str, Any] = {
        "items": [user.model_dump() for user in users],
        "total": total,  # None when true total is unknown
        "count": len(users),
        "page": page,
        "per_page": per_page,
        "offset": (page - 1) * per_page,
        "has_more": len(users) == per_page,  # heuristic when total unknown
        "next_page": page + 1 if len(users) == per_page else None,
        "next_offset": page * per_page if len(users) == per_page else None,
        "_meta": {},  # Pre-allocated for truncation flags
    }

    return json.dumps(response, indent=2, default=str)


def _format_organizations_markdown(orgs: list[Organization], query_info: str = "Search Results") -> str:
    """Format organizations as markdown for human readability.

    Args:
        orgs: List of organizations to format
        query_info: Description of the query/search

    Returns:
        Markdown-formatted string
    """
    lines = [f"# Organization Search Results: {query_info}", ""]
    lines.append(f"Found {len(orgs)} organization(s)")
    lines.append("")

    for org in orgs:
        lines.append(f"## {org.name}")
        lines.append(f"- **ID**: {org.id}")
        lines.append(f"- **Active**: {org.active}")
        lines.append("")

    return "\n".join(lines)


def _format_organizations_json(orgs: list[Organization], total: int | None, page: int, per_page: int) -> str:
    """Format organizations as JSON for programmatic processing.

    Args:
        orgs: List of organizations to format
        total: Total count of matching organizations across all pages (None if unknown)
        page: Current page number
        per_page: Results per page

    Returns:
        JSON-formatted string with pagination metadata
    """
    response: dict[str, Any] = {
        "items": [org.model_dump() for org in orgs],
        "total": total,  # None when true total is unknown
        "count": len(orgs),
        "page": page,
        "per_page": per_page,
        "offset": (page - 1) * per_page,
        "has_more": len(orgs) == per_page,  # heuristic when total unknown
        "next_page": page + 1 if len(orgs) == per_page else None,
        "next_offset": page * per_page if len(orgs) == per_page else None,
        "_meta": {},  # Pre-allocated for truncation flags
    }

    return json.dumps(response, indent=2, default=str)


def _format_list_markdown(items: list[T], item_type: str) -> str:
    """Format a generic list as markdown for human readability.

    Args:
        items: List of items to format (must have id, name, and model_dump())
        item_type: Type of items (e.g., "Group", "State", "Priority")

    Returns:
        Markdown-formatted string
    """
    # Sort items by id for stable ordering
    sorted_items = sorted(items, key=lambda x: x.id)

    lines = [f"# {item_type} List", ""]
    lines.append(f"Found {len(sorted_items)} {item_type.lower()}(s)")
    lines.append("")

    for item in sorted_items:
        lines.append(f"- **{item.name}** (ID: {item.id})")

    return "\n".join(lines)


def _format_list_json(items: list[T]) -> str:
    """Format a generic list as JSON for programmatic processing.

    Args:
        items: List of items to format (must have id, name, and model_dump())

    Returns:
        JSON-formatted string with pagination metadata
    """
    # Sort items by id for stable ordering
    sorted_items = sorted(items, key=lambda x: x.id)

    # Since these are complete cached lists, pagination shows all items on page 1
    total = len(sorted_items)
    page = 1
    per_page = total
    offset = 0

    response: dict[str, Any] = {
        "items": [item.model_dump() for item in sorted_items],  # type: ignore[attr-defined]
        "total": total,
        "count": total,
        "page": page,
        "per_page": per_page,
        "offset": offset,
        "has_more": False,  # Always false for complete lists
        "next_page": None,
        "next_offset": None,
        "_meta": {},  # Pre-allocated for truncation flags
    }

    return json.dumps(response, indent=2, default=str)


def _handle_api_error(e: Exception, context: str = "operation") -> str:
    """Format errors with actionable guidance for LLM agents.

    Args:
        e: The exception that occurred
        context: Description of what was being attempted

    Returns:
        Formatted error message with guidance
    """
    error_msg = str(e).lower()

    # Check for specific error patterns
    if "not found" in error_msg or "404" in error_msg:
        return f"Error: Resource not found during {context}. Please verify the ID is correct and you have access."

    if "forbidden" in error_msg or "403" in error_msg:
        return f"Error: Permission denied for {context}. Your credentials lack access to this resource."

    if "unauthorized" in error_msg or "401" in error_msg:
        return f"Error: Authentication failed for {context}. Check ZAMMAD_HTTP_TOKEN is valid."

    if "timeout" in error_msg:
        return f"Error: Request timeout during {context}. The server may be slow - try again or reduce the scope."

    if "connection" in error_msg or "network" in error_msg:
        return f"Error: Network issue during {context}. Check ZAMMAD_URL is correct and the server is reachable."

    # Generic error with type information
    return f"Error during {context}: {type(e).__name__} - {e}"


class ZammadMCPServer:
    """Zammad MCP Server with proper client lifecycle management."""

    def __init__(self) -> None:
        """Initialize the server."""
        self.client: ZammadClient | None = None
        # Create FastMCP with lifespan configured
        self.mcp = FastMCP("Zammad MCP Server", lifespan=self._create_lifespan())
        self._setup_tools()
        self._setup_resources()
        self._setup_prompts()

    def _create_lifespan(self) -> Any:
        """Create the lifespan context manager for the server."""

        @asynccontextmanager
        async def lifespan(_app: FastMCP) -> AsyncIterator[None]:
            """Initialize resources on startup and cleanup on shutdown."""
            await self.initialize()
            try:
                yield
            finally:
                if self.client is not None:
                    self.client = None
                    logger.info("Zammad client cleaned up")

        return lifespan

    def get_client(self) -> ZammadClient:
        """Get the Zammad client, ensuring it's initialized."""
        if not self.client:
            raise RuntimeError("Zammad client not initialized")
        return self.client

    async def initialize(self) -> None:
        """Initialize the Zammad client on server startup."""
        # Load environment variables from .env files
        # First, try to load from current working directory
        cwd_env = Path.cwd() / ".env"
        if cwd_env.exists():
            load_dotenv(cwd_env)
            logger.info("Loaded environment from %s", cwd_env)

        # Then, try to load from .envrc if it exists and convert to .env format
        envrc_path = Path.cwd() / ".envrc"
        if envrc_path.exists() and not os.environ.get("ZAMMAD_URL"):
            # If .envrc exists but env vars aren't set, warn the user
            logger.warning(
                "Found .envrc but environment variables not loaded. Consider using direnv or creating a .env file"
            )

        # Also support loading from parent directories (for when running from subdirs)
        load_dotenv()

        try:
            self.client = ZammadClient()
            logger.info("Zammad client initialized successfully")

            # Test connection
            current_user = self.client.get_current_user()
            logger.info("Connected as user ID: %s", current_user.get("id", "unknown"))
        except Exception:
            logger.exception("Failed to initialize Zammad client")
            raise

    def _setup_tools(self) -> None:
        """Register all tools with the MCP server."""
        self._setup_ticket_tools()
        self._setup_user_org_tools()
        self._setup_system_tools()

    def _setup_ticket_tools(self) -> None:  # noqa: PLR0915
        """Register ticket-related tools."""

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_search_tickets(params: TicketSearchParams) -> str:
            """Search for tickets with various filters.

            Args:
                params: Search parameters including filters and pagination

            Returns:
                Formatted response in either JSON or Markdown format
            """
            client = self.get_client()

            # Extract search parameters (exclude response_format for API call)
            search_params = params.model_dump(exclude={"response_format"}, exclude_none=True)
            tickets_data = client.search_tickets(**search_params)

            tickets = [Ticket(**ticket) for ticket in tickets_data]

            # Build query info string
            filter_parts = {
                "query": params.query,
                "state": params.state,
                "priority": params.priority,
                "group": params.group,
                "owner": params.owner,
                "customer": params.customer,
            }
            filters = [f"{k}='{v}'" for k, v in filter_parts.items() if v]
            query_info = ", ".join(filters) if filters else "All tickets"

            # Format response
            if params.response_format == ResponseFormat.JSON:
                result = _format_tickets_json(tickets, None, params.page, params.per_page)
            else:
                result = _format_tickets_markdown(tickets, query_info)

            return truncate_response(result)

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_get_ticket(params: GetTicketParams) -> Ticket:
            """Get detailed information about a specific ticket.

            Args:
                params: Get ticket parameters including ticket_id and article options.
                       ticket_id must be the internal database ID (NOT the display number).
                       Use the 'id' field from search results, not the 'number' field.
                       Example: For "Ticket #65003", use the 'id' value from search results.

            Returns:
                Ticket details including articles if requested

            Note: Large tickets with many articles may exceed token limits. Use article_limit
            to control the response size. Articles are returned in chronological order.
            """
            client = self.get_client()
            try:
                ticket_data = client.get_ticket(
                    ticket_id=params.ticket_id,
                    include_articles=params.include_articles,
                    article_limit=params.article_limit,
                    article_offset=params.article_offset,
                )
                return Ticket(**ticket_data)
            except Exception as e:
                error_msg = str(e).lower()
                if "not found" in error_msg or "couldn't find" in error_msg:
                    raise TicketIdGuidanceError(params.ticket_id) from e
                raise

        @self.mcp.tool(
            annotations={
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        )
        def zammad_create_ticket(params: TicketCreate) -> Ticket:
            """Create a new ticket in Zammad.

            Args:
                params: Ticket creation parameters

            Returns:
                The created ticket
            """
            client = self.get_client()
            ticket_data = client.create_ticket(**params.model_dump(exclude_none=True, mode="json"))

            return Ticket(**ticket_data)

        @self.mcp.tool(
            annotations={
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        )
        def zammad_update_ticket(params: TicketUpdateParams) -> Ticket:
            """Update an existing ticket.

            Args:
                params: Ticket update parameters including ticket_id and fields to update.
                       ticket_id must be the internal database ID (NOT the display number).
                       Use the 'id' field from search results, not the 'number' field.
                       Example: For "Ticket #65003", use the 'id' value from search results.

            Returns:
                The updated ticket
            """
            client = self.get_client()
            try:
                # Extract ticket_id and update fields separately
                update_data = params.model_dump(exclude={"ticket_id"}, exclude_none=True)
                ticket_data = client.update_ticket(ticket_id=params.ticket_id, **update_data)
                return Ticket(**ticket_data)
            except Exception as e:
                error_msg = str(e).lower()
                if "not found" in error_msg or "couldn't find" in error_msg:
                    raise TicketIdGuidanceError(params.ticket_id) from e
                raise

        @self.mcp.tool(
            annotations={
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        )
        def zammad_add_article(params: ArticleCreate) -> Article:
            """Add an article (comment/note) to a ticket.

            Args:
                params: Article creation parameters including ticket_id.
                       ticket_id must be the internal database ID (NOT the display number).
                       Use the 'id' field from search results, not the 'number' field.
                       Example: For "Ticket #65003", use the 'id' value from search results.

            Returns:
                The created article
            """
            client = self.get_client()
            # Extract ticket_id and article_type separately to avoid duplicate kwargs
            # Use mode="json" to convert enums to strings, by_alias=True for API compatibility
            article_params = params.model_dump(mode="json", by_alias=True, exclude={"ticket_id", "article_type"})
            article_data = client.add_article(
                ticket_id=params.ticket_id, article_type=params.article_type.value, **article_params
            )

            return Article(**article_data)

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_get_article_attachments(params: GetArticleAttachmentsParams) -> list[Attachment]:
            """Get list of attachments for a ticket article.

            Args:
                params: Article attachments request parameters including ticket_id.
                       ticket_id must be the internal database ID (NOT the display number).
                       Use the 'id' field from search results, not the 'number' field.
                       Example: For "Ticket #65003", use the 'id' value from search results.

            Returns:
                List of attachment information
            """
            client = self.get_client()
            attachments_data = client.get_article_attachments(params.ticket_id, params.article_id)
            return [Attachment(**attachment) for attachment in attachments_data]

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_download_attachment(params: DownloadAttachmentParams) -> str:
            """Download an attachment from a ticket article.

            Args:
                params: Download attachment parameters including ticket_id.
                       ticket_id must be the internal database ID (NOT the display number).
                       Use the 'id' field from search results, not the 'number' field.
                       Example: For "Ticket #65003", use the 'id' value from search results.

            Returns:
                Base64-encoded attachment content

            Raises:
                AttachmentDownloadError: If attachment download fails or exceeds max_bytes
            """
            client = self.get_client()
            try:
                attachment_data = client.download_attachment(params.ticket_id, params.article_id, params.attachment_id)
            except (requests.exceptions.RequestException, ValueError, AttachmentDownloadError) as e:
                raise AttachmentDownloadError(
                    ticket_id=params.ticket_id,
                    article_id=params.article_id,
                    attachment_id=params.attachment_id,
                    original_error=e,
                ) from e

            # Guard against very large attachments
            if params.max_bytes is not None and len(attachment_data) > params.max_bytes:
                raise AttachmentDownloadError(
                    ticket_id=params.ticket_id,
                    article_id=params.article_id,
                    attachment_id=params.attachment_id,
                    original_error=ValueError(
                        f"Attachment size {len(attachment_data)} bytes exceeds max_bytes={params.max_bytes}"
                    ),
                )

            # Convert bytes to base64 string for transmission
            return base64.b64encode(attachment_data).decode("utf-8")

        @self.mcp.tool(
            annotations={
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_add_ticket_tag(params: TagOperationParams) -> TagOperationResult:
            """Add a tag to a ticket.

            Args:
                params: Tag operation parameters including ticket_id.
                       ticket_id must be the internal database ID (NOT the display number).
                       Use the 'id' field from search results, not the 'number' field.
                       Example: For "Ticket #65003", use the 'id' value from search results.

            Returns:
                Operation result with success status
            """
            client = self.get_client()
            result = client.add_ticket_tag(params.ticket_id, params.tag)
            return TagOperationResult(**result)

        @self.mcp.tool(
            annotations={
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_remove_ticket_tag(params: TagOperationParams) -> TagOperationResult:
            """Remove a tag from a ticket.

            Args:
                params: Tag operation parameters including ticket_id.
                       ticket_id must be the internal database ID (NOT the display number).
                       Use the 'id' field from search results, not the 'number' field.
                       Example: For "Ticket #65003", use the 'id' value from search results.

            Returns:
                Operation result with success status
            """
            client = self.get_client()
            result = client.remove_ticket_tag(params.ticket_id, params.tag)
            return TagOperationResult(**result)

    def _setup_user_org_tools(self) -> None:
        """Register user and organization tools."""

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_get_user(params: GetUserParams) -> User:
            """Get user information by ID.

            Args:
                params: Get user parameters

            Returns:
                User details
            """
            client = self.get_client()
            user_data = client.get_user(params.user_id)
            return User(**user_data)

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_search_users(params: SearchUsersParams) -> str:
            """Search for users.

            Args:
                params: Search users parameters

            Returns:
                Formatted response in either JSON or Markdown format
            """
            client = self.get_client()
            users_data = client.search_users(query=params.query, page=params.page, per_page=params.per_page)
            users = [User(**user) for user in users_data]

            # Format response
            if params.response_format == ResponseFormat.JSON:
                result = _format_users_json(users, None, params.page, params.per_page)
            else:
                result = _format_users_markdown(users, f"query='{params.query}'")

            return truncate_response(result)

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_get_organization(params: GetOrganizationParams) -> Organization:
            """Get organization information by ID.

            Args:
                params: Get organization parameters

            Returns:
                Organization details
            """
            client = self.get_client()
            org_data = client.get_organization(params.org_id)
            return Organization(**org_data)

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_search_organizations(params: SearchOrganizationsParams) -> str:
            """Search for organizations.

            Args:
                params: Search organizations parameters

            Returns:
                Formatted response in either JSON or Markdown format
            """
            client = self.get_client()
            orgs_data = client.search_organizations(query=params.query, page=params.page, per_page=params.per_page)
            orgs = [Organization(**org) for org in orgs_data]

            # Format response
            if params.response_format == ResponseFormat.JSON:
                result = _format_organizations_json(orgs, None, params.page, params.per_page)
            else:
                result = _format_organizations_markdown(orgs, f"query='{params.query}'")

            return truncate_response(result)

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_get_current_user() -> User:
            """Get information about the currently authenticated user.

            Returns:
                Current user details
            """
            client = self.get_client()
            user_data = client.get_current_user()
            return User(**user_data)

    def _get_cached_groups(self) -> list[Group]:
        """Get cached list of groups."""
        if not hasattr(self, "_groups_cache"):
            client = self.get_client()
            groups_data = client.get_groups()
            self._groups_cache = [Group(**group) for group in groups_data]
        return self._groups_cache

    def _get_cached_states(self) -> list[TicketState]:
        """Get cached list of ticket states."""
        if not hasattr(self, "_states_cache"):
            client = self.get_client()
            states_data = client.get_ticket_states()
            self._states_cache = [TicketState(**state) for state in states_data]
        return self._states_cache

    def _get_cached_priorities(self) -> list[TicketPriority]:
        """Get cached list of ticket priorities."""
        if not hasattr(self, "_priorities_cache"):
            client = self.get_client()
            priorities_data = client.get_ticket_priorities()
            self._priorities_cache = [TicketPriority(**priority) for priority in priorities_data]
        return self._priorities_cache

    def clear_caches(self) -> None:
        """Clear all cached data."""
        if hasattr(self, "_groups_cache"):
            del self._groups_cache
        if hasattr(self, "_states_cache"):
            del self._states_cache
        if hasattr(self, "_priorities_cache"):
            del self._priorities_cache
        if hasattr(self, "_state_type_mapping"):
            del self._state_type_mapping

    @staticmethod
    def _extract_state_name(ticket: dict[str, Any]) -> str:
        """Extract state name from a ticket, handling both string and dict formats.

        Args:
            ticket: Ticket data dictionary

        Returns:
            State name as a string
        """
        state = ticket.get("state")
        if isinstance(state, str):
            return state
        if isinstance(state, dict):
            return str(state.get("name", ""))
        return ""

    @staticmethod
    def _is_ticket_escalated(ticket: dict[str, Any]) -> bool:
        """Check if a ticket is escalated.

        Args:
            ticket: Ticket data dictionary

        Returns:
            True if ticket has any escalation time set
        """
        return bool(
            ticket.get("first_response_escalation_at")
            or ticket.get("close_escalation_at")
            or ticket.get("update_escalation_at")
        )

    def _get_state_type_mapping(self) -> dict[str, int]:
        """Get mapping of state names to state_type_id.

        Returns:
            Dictionary mapping state name to state_type_id
        """
        if not hasattr(self, "_state_type_mapping"):
            states = self._get_cached_states()
            self._state_type_mapping = {state.name: state.state_type_id for state in states}
        return self._state_type_mapping

    def _categorize_ticket_state(self, state_name: str) -> tuple[int, int, int]:
        """Categorize a ticket state into open/closed/pending counters.

        Args:
            state_name: Name of the ticket state

        Returns:
            Tuple of (open_increment, closed_increment, pending_increment)

        Note:
            Uses state_type_id from Zammad instead of string matching:
            - 1 (new), 2 (open) -> open
            - 3 (closed) -> closed
            - 4 (pending reminder), 5 (pending close) -> pending
        """
        state_type_mapping = self._get_state_type_mapping()
        state_type_id = state_type_mapping.get(state_name, 0)

        # Categorize based on state_type_id
        if state_type_id in [STATE_TYPE_NEW, STATE_TYPE_OPEN]:
            return (1, 0, 0)
        if state_type_id == STATE_TYPE_CLOSED:
            return (0, 1, 0)
        if state_type_id in [STATE_TYPE_PENDING_REMINDER, STATE_TYPE_PENDING_CLOSE]:
            return (0, 0, 1)
        return (0, 0, 0)

    def _process_ticket_batch(self, tickets: list[dict[str, Any]]) -> tuple[int, int, int, int, int]:
        """Process a batch of tickets and return updated counters.

        Args:
            tickets: List of ticket dictionaries to process

        Returns:
            Tuple of (total, open, closed, pending, escalated) counts for this batch
        """
        batch_total = len(tickets)
        batch_open = 0
        batch_closed = 0
        batch_pending = 0
        batch_escalated = 0

        for ticket in tickets:
            state_name = self._extract_state_name(ticket)
            open_inc, closed_inc, pending_inc = self._categorize_ticket_state(state_name)

            batch_open += open_inc
            batch_closed += closed_inc
            batch_pending += pending_inc

            if self._is_ticket_escalated(ticket):
                batch_escalated += 1

        return batch_total, batch_open, batch_closed, batch_pending, batch_escalated

    def _collect_ticket_stats_paginated(
        self, client: ZammadClient, group: str | None
    ) -> tuple[int, int, int, int, int, int]:
        """Collect ticket statistics using pagination.

        Args:
            client: Zammad client instance
            group: Optional group filter

        Returns:
            Tuple of (total, open, closed, pending, escalated, pages) counts
        """
        total_count = 0
        open_count = 0
        closed_count = 0
        pending_count = 0
        escalated_count = 0
        page = 1
        per_page = MAX_PER_PAGE

        while True:
            tickets = client.search_tickets(group=group, page=page, per_page=per_page)

            if not tickets:
                break

            batch_total, batch_open, batch_closed, batch_pending, batch_escalated = self._process_ticket_batch(tickets)
            total_count += batch_total
            open_count += batch_open
            closed_count += batch_closed
            pending_count += batch_pending
            escalated_count += batch_escalated

            page += 1

            if page > MAX_PAGES_FOR_TICKET_SCAN:
                logger.warning(
                    "Reached maximum page limit (%s pages), processed %s tickets - some tickets may not be counted",
                    MAX_PAGES_FOR_TICKET_SCAN,
                    total_count,
                )
                break

        return total_count, open_count, closed_count, pending_count, escalated_count, page - 1

    def _build_stats_result(
        self,
        total: int,
        open_count: int,
        closed: int,
        pending: int,
        escalated: int,
        pages: int,
        elapsed: float,
    ) -> TicketStats:
        """Build and log ticket statistics result.

        Args:
            total: Total ticket count
            open_count: Open ticket count
            closed: Closed ticket count
            pending: Pending ticket count
            escalated: Escalated ticket count
            pages: Number of pages processed
            elapsed: Elapsed time in seconds

        Returns:
            TicketStats object
        """
        logger.info(
            "Ticket statistics complete: processed %s tickets across %s pages in %.2fs "
            "(open=%s, closed=%s, pending=%s, escalated=%s)",
            total,
            pages,
            elapsed,
            open_count,
            closed,
            pending,
            escalated,
        )

        return TicketStats(
            total_count=total,
            open_count=open_count,
            closed_count=closed,
            pending_count=pending,
            escalated_count=escalated,
            avg_first_response_time=None,
            avg_resolution_time=None,
        )

    def _setup_system_tools(self) -> None:
        """Register system information tools."""

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_get_ticket_stats(params: GetTicketStatsParams) -> TicketStats:
            """Get ticket statistics using pagination for better performance.

            Args:
                params: Ticket statistics parameters

            Returns:
                Ticket statistics

            Note: This implementation uses pagination to avoid loading all tickets
            into memory at once, improving performance for large datasets.
            """
            start_time = time.time()
            client = self.get_client()

            if params.start_date or params.end_date:
                logger.warning("Date filtering not yet implemented - ignoring date parameters")

            group_filter_msg = f" for group '{params.group}'" if params.group else ""
            logger.info("Starting ticket statistics calculation%s", group_filter_msg)

            total, open_count, closed, pending, escalated, pages = self._collect_ticket_stats_paginated(
                client, params.group
            )

            return self._build_stats_result(
                total, open_count, closed, pending, escalated, pages, time.time() - start_time
            )

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_list_groups(params: ListParams) -> str:
            """Get all available groups (cached).

            Args:
                params: List parameters

            Returns:
                Formatted response in either JSON or Markdown format
            """
            groups = self._get_cached_groups()

            # Format response
            if params.response_format == ResponseFormat.JSON:
                result = _format_list_json(groups)
            else:
                result = _format_list_markdown(groups, "Group")

            return truncate_response(result)

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_list_ticket_states(params: ListParams) -> str:
            """Get all available ticket states (cached).

            Args:
                params: List parameters

            Returns:
                Formatted response in either JSON or Markdown format
            """
            states = self._get_cached_states()

            # Format response
            if params.response_format == ResponseFormat.JSON:
                result = _format_list_json(states)
            else:
                result = _format_list_markdown(states, "Ticket State")

            return truncate_response(result)

        @self.mcp.tool(
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        )
        def zammad_list_ticket_priorities(params: ListParams) -> str:
            """Get all available ticket priorities (cached).

            Args:
                params: List parameters

            Returns:
                Formatted response in either JSON or Markdown format
            """
            priorities = self._get_cached_priorities()

            # Format response
            if params.response_format == ResponseFormat.JSON:
                result = _format_list_json(priorities)
            else:
                result = _format_list_markdown(priorities, "Ticket Priority")

            return truncate_response(result)

    def _setup_resources(self) -> None:
        """Register all resources with the MCP server."""
        self._setup_ticket_resource()
        self._setup_user_resource()
        self._setup_organization_resource()
        self._setup_queue_resource()

    def _setup_ticket_resource(self) -> None:
        """Register ticket resource."""

        @self.mcp.resource("zammad://ticket/{ticket_id}")
        def get_ticket_resource(ticket_id: str) -> str:
            """Get a ticket as a resource."""
            client = self.get_client()
            try:
                # Use a reasonable limit for resources to avoid huge responses
                ticket_data = client.get_ticket(int(ticket_id), include_articles=True, article_limit=20)
                ticket = Ticket(**ticket_data)

                # Normalize possibly-expanded fields using helper
                state_name = _brief_field(ticket.state, "name")
                priority_name = _brief_field(ticket.priority, "name")
                customer_email = _brief_field(ticket.customer, "email")

                # Format ticket data as readable text
                lines = [
                    f"Ticket #{ticket.number} - {ticket.title}",
                    f"ID: {ticket.id}",
                    f"State: {state_name}",
                    f"Priority: {priority_name}",
                    f"Customer: {customer_email}",
                    f"Created: {ticket.created_at.isoformat()}",
                    "",
                    "Articles:",
                    "",
                ]

                # Handle articles if present
                if ticket.articles:
                    for article in ticket.articles:
                        created_by_email = _brief_field(article.created_by, "email")
                        lines.extend(
                            [
                                f"--- {article.created_at.isoformat()} by {created_by_email} ---",
                                _escape_article_body(article),
                                "",
                            ]
                        )

                return truncate_response("\n".join(lines))
            except (requests.exceptions.RequestException, ValueError, ValidationError) as e:
                return _handle_api_error(e, context=f"retrieving ticket {ticket_id}")

    def _setup_user_resource(self) -> None:
        """Register user resource."""

        @self.mcp.resource("zammad://user/{user_id}")
        def get_user_resource(user_id: str) -> str:
            """Get a user as a resource."""
            client = self.get_client()
            try:
                user = client.get_user(int(user_id))

                lines = [
                    f"User: {user.get('firstname', '')} {user.get('lastname', '')}",
                    f"Email: {user.get('email', '')}",
                    f"Login: {user.get('login', '')}",
                    f"Organization: {user.get('organization', {}).get('name', 'None')}",
                    f"Active: {user.get('active', False)}",
                    f"VIP: {user.get('vip', False)}",
                    f"Created: {user.get('created_at', 'Unknown')}",
                ]

                return "\n".join(lines)
            except (requests.exceptions.RequestException, ValueError, ValidationError) as e:
                return _handle_api_error(e, context=f"retrieving user {user_id}")

    def _setup_organization_resource(self) -> None:
        """Register organization resource."""

        @self.mcp.resource("zammad://organization/{org_id}")
        def get_organization_resource(org_id: str) -> str:
            """Get an organization as a resource."""
            client = self.get_client()
            try:
                org = client.get_organization(int(org_id))

                lines = [
                    f"Organization: {org.get('name', '')}",
                    f"Domain: {org.get('domain', 'None')}",
                    f"Active: {org.get('active', False)}",
                    f"Note: {org.get('note', 'None')}",
                    f"Created: {org.get('created_at', 'Unknown')}",
                ]

                return "\n".join(lines)
            except (requests.exceptions.RequestException, ValueError, ValidationError) as e:
                return _handle_api_error(e, context=f"retrieving organization {org_id}")

    def _setup_queue_resource(self) -> None:
        """Register queue resource."""

        @self.mcp.resource("zammad://queue/{group}")
        def get_queue_resource(group: str) -> str:
            """Get ticket queue for a specific group as a resource."""
            client = self.get_client()
            try:
                # Search for tickets in the specified group with various states
                tickets = client.search_tickets(group=group, per_page=50)

                if not tickets:
                    return f"Queue for group '{group}': No tickets found"

                # Organize tickets by state
                ticket_states: dict[str, list[dict[str, Any]]] = {}
                for ticket in tickets:
                    state_name = self._extract_state_name(ticket)

                    if state_name not in ticket_states:
                        ticket_states[state_name] = []
                    ticket_states[state_name].append(ticket)

                lines = [
                    f"Queue for Group: {group}",
                    f"Total Tickets: {len(tickets)}",
                    "",
                ]

                # Add summary by state
                for state, state_tickets in sorted(ticket_states.items()):
                    lines.append(f"{state.title()} ({len(state_tickets)} tickets):")
                    for ticket in state_tickets[:MAX_TICKETS_PER_STATE_IN_QUEUE]:  # Show first N tickets per state
                        priority = ticket.get("priority", {})
                        priority_name = priority.get("name", "Unknown") if isinstance(priority, dict) else str(priority)
                        customer = ticket.get("customer", {})
                        customer_email = (
                            customer.get("email", "Unknown") if isinstance(customer, dict) else str(customer)
                        )

                        title = str(ticket.get("title", "No title"))
                        short = title[:50]
                        suffix = "..." if len(title) > len(short) else ""
                        lines.append(
                            f"  #{ticket.get('number', 'N/A')} (ID: {ticket.get('id', 'N/A')}) - {short}{suffix}"
                        )
                        lines.append(f"    Priority: {priority_name}, Customer: {customer_email}")
                        lines.append(f"    Created: {ticket.get('created_at', 'Unknown')}")

                    if len(state_tickets) > MAX_TICKETS_PER_STATE_IN_QUEUE:
                        lines.append(f"    ... and {len(state_tickets) - MAX_TICKETS_PER_STATE_IN_QUEUE} more tickets")
                    lines.append("")

                return truncate_response("\n".join(lines))
            except (requests.exceptions.RequestException, ValueError, ValidationError) as e:
                return _handle_api_error(e, context=f"retrieving queue for group '{group}'")

    def _setup_prompts(self) -> None:
        """Register all prompts with the MCP server."""

        @self.mcp.prompt()
        def analyze_ticket(ticket_id: int) -> str:
            """Generate a prompt to analyze a ticket.

            Note: ticket_id must be the internal database ID (NOT the display number).
            Use the 'id' field from search results, not the 'number' field.
            Example: For "Ticket #65003", use the 'id' value from search results.
            """
            return f"""Please analyze ticket with ID {ticket_id} from Zammad.
Use the zammad_get_ticket tool to retrieve the ticket details including all articles.

After retrieving the ticket, provide:
1. A summary of the issue
2. Current status and priority
3. Timeline of interactions
4. Suggested next steps or resolution

Use appropriate tools to gather any additional context about the customer or organization if needed."""

        @self.mcp.prompt()
        def draft_response(ticket_id: int, tone: str = "professional") -> str:
            """Generate a prompt to draft a response to a ticket.

            Note: ticket_id must be the internal database ID (NOT the display number).
            Use the 'id' field from search results, not the 'number' field.
            Example: For "Ticket #65003", use the 'id' value from search results.
            """
            return f"""Please help draft a {tone} response to ticket with ID {ticket_id}.

First, use zammad_get_ticket to understand the issue and conversation history. Then draft an appropriate response that:
1. Acknowledges the customer's concern
2. Provides a clear solution or next steps
3. Maintains a {tone} tone throughout
4. Is concise and easy to understand

After drafting, you can use zammad_add_article to add the response to the ticket if approved."""

        @self.mcp.prompt()
        def escalation_summary(group: str | None = None) -> str:
            """Generate a prompt to summarize escalated tickets."""
            group_filter = f" for group '{group}'" if group else ""
            return f"""Please provide a summary of escalated tickets{group_filter}.

Use zammad_search_tickets to find tickets with escalation times set. For each escalated ticket:
1. Ticket number and title
2. Escalation type (first response, update, or close)
3. Time until escalation
4. Current assignee
5. Recommended action

Organize the results by urgency and provide actionable recommendations."""


# Create the server instance
server = ZammadMCPServer()

# Export the MCP server instance
mcp = server.mcp


def _configure_logging() -> None:
    """Configure logging from LOG_LEVEL environment variable.

    Reads LOG_LEVEL environment variable (default: INFO) and configures
    the root logger. Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL.
    """
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    if log_level_str not in valid_levels:
        invalid_level = log_level_str  # Store before resetting
        log_level_str = "INFO"
        logger.warning(
            "Invalid LOG_LEVEL '%s', defaulting to INFO. Valid values: %s",
            invalid_level,
            ", ".join(valid_levels),
        )

    log_level = getattr(logging, log_level_str)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Add handler if none exists
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        root_logger.addHandler(handler)


def main() -> None:
    """Main entry point for the server."""
    _configure_logging()
    mcp.run()
