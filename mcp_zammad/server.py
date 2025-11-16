"""Zammad MCP Server implementation."""

import base64
import html
import json
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn, Protocol, TypeVar

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
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

    def model_dump(self) -> dict[str, Any]: ...  # codacy: ignore E704


T = TypeVar("T", bound=_Dumpable)

# Configure logging
logger = logging.getLogger(__name__)

# Constants
MAX_PAGES_FOR_TICKET_SCAN = 1000
MAX_TICKETS_PER_STATE_IN_QUEUE = 10
MAX_PER_PAGE = 100  # Maximum results per page for pagination
CHARACTER_LIMIT = 25000  # Maximum response size per MCP best practices
ARTICLE_BODY_TRUNCATE_LENGTH = 500  # Maximum length for article body in markdown formatting

# Zammad state type IDs (from Zammad API)
STATE_TYPE_NEW = 1
STATE_TYPE_OPEN = 2
STATE_TYPE_CLOSED = 3
STATE_TYPE_PENDING_REMINDER = 4
STATE_TYPE_PENDING_CLOSE = 5


# Tool annotation constants
def _read_only_annotations(title: str) -> ToolAnnotations:
    """Create read-only tool annotations with title."""
    return ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
        title=title,
    )


def _write_annotations(title: str) -> ToolAnnotations:
    """Create write tool annotations with title."""
    return ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
        title=title,
    )


def _idempotent_write_annotations(title: str) -> ToolAnnotations:
    """Create idempotent write tool annotations with title."""
    return ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
        title=title,
    )


def _handle_ticket_not_found_error(ticket_id: int, error: Exception) -> NoReturn:
    """Check if an exception is a ticket not found error and raise TicketIdGuidanceError.

    Args:
        ticket_id: The ticket ID that was not found
        error: The exception to check

    Raises:
        TicketIdGuidanceError: If the error is a not found error
        Exception: Re-raises the original error if not a not found error
    """
    error_msg = str(error).lower()
    if "not found" in error_msg or "couldn't find" in error_msg:
        raise TicketIdGuidanceError(ticket_id) from error
    raise error


def _brief_field(value: object, attr: str) -> str:
    """Extract a field from a Brief model or return Unknown.

    Handles StateBrief, PriorityBrief, UserBrief objects or string fallbacks.

    Args:
        value: The value to extract from (Brief model, string, or None)
        attr: The attribute name to extract

    Returns:
        The extracted value or "Unknown"
    """
    if isinstance(value, StateBrief | PriorityBrief | UserBrief):
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


def _serialize_json(obj: dict[str, Any], *, use_compact: bool) -> str:
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


def _find_max_items_for_limit(obj: dict[str, Any], original_items: list[Any], limit: int, *, use_compact: bool) -> int:
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
        if len(_serialize_json(obj, use_compact=use_compact)) <= limit:
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

    # Attempt to shrink common list fields if present
    candidate_arrays: tuple[str, ...] = ("items", "articles", "members")
    for key in candidate_arrays:
        if key in obj and isinstance(obj[key], list):
            original_items = obj[key]
            max_items = _find_max_items_for_limit(obj, original_items, limit, use_compact=use_compact)
            obj[key] = original_items[:max_items]

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

    # Ensure final JSON fits under limit by trimming the largest list field
    json_str = _serialize_json(obj, use_compact=use_compact)
    if len(json_str) <= limit:
        return json_str
    # Identify the largest list among candidates and trim further
    largest_key = max(
        (k for k in candidate_arrays if isinstance(obj.get(k), list)),
        key=lambda k: len(obj.get(k, [])),  # type: ignore[arg-type]
        default=None,
    )
    if largest_key:
        while obj[largest_key] and len(json_str) > limit:  # type: ignore[index]
            obj[largest_key].pop()  # type: ignore[index]
            json_str = _serialize_json(obj, use_compact=use_compact)
    return json_str


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
    if content.lstrip().startswith(("{", "[")):
        try:
            obj = json.loads(content)
            return _truncate_json_response(content, obj, limit)
        except (json.JSONDecodeError, TypeError) as e:
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


def _normalize_datetime_to_iso(value: object) -> str:
    """Normalize datetime value to ISO 8601 string format."""
    if isinstance(value, datetime):
        return value.isoformat()
    if value:
        return str(value)
    return "Unknown"


def _extract_article_fields(article: dict | Article) -> tuple[str, str, object, str, str]:
    """Extract fields from article (dict or Article object) with defensive handling.

    Returns:
        Tuple of (from_field, type_field, created_at_raw, body, content_type)
    """
    if isinstance(article, dict):
        from_field = article.get("from", "Unknown")
        type_field = article.get("type", "Unknown")
        created_at_raw = article.get("created_at")
        body = article.get("body", "")
        content_type = article.get("content_type") or article.get("content-type", "text/plain")
    else:
        # Article object - use attribute access
        from_field = article.from_ or "Unknown"
        type_field = article.type
        created_at_raw = article.created_at
        body = article.body
        content_type = getattr(article, "content_type", "text/plain")

    return from_field, type_field, created_at_raw, body, content_type


def _format_ticket_articles_section(articles: list) -> list[str]:
    """Build articles section for ticket markdown."""
    if not articles:
        return []

    lines = ["## Articles", ""]
    for i, article in enumerate(articles, 1):
        lines.append(f"### Article {i}")

        # Extract fields with defensive dict/object handling
        from_field, type_field, created_at_raw, body, content_type = _extract_article_fields(article)

        # Normalize created_at to ISO 8601 format
        created_at = _normalize_datetime_to_iso(created_at_raw)

        # Escape HTML content to prevent XSS injection in markdown renderers
        if "html" in content_type.lower():
            body = html.escape(body)

        lines.append(f"- **From**: {from_field}")
        lines.append(f"- **Type**: {type_field}")
        lines.append(f"- **Created**: {created_at}")
        lines.append("")
        # Truncate very long bodies (after escaping to preserve safety)
        if len(body) > ARTICLE_BODY_TRUNCATE_LENGTH:
            body = body[:ARTICLE_BODY_TRUNCATE_LENGTH] + "...\n(truncated)"
        lines.append(body)
        lines.append("")
    return lines


def _format_ticket_detail_markdown(ticket: Ticket) -> str:
    """Format single ticket with full details as markdown.

    Args:
        ticket: Ticket object to format

    Returns:
        Markdown-formatted string
    """
    lines = [f"# Ticket #{ticket.number} - {ticket.title}", ""]
    lines.append(f"**ID**: {ticket.id}")
    lines.append(f"**State**: {_brief_field(ticket.state, 'name')}")
    lines.append(f"**Priority**: {_brief_field(ticket.priority, 'name')}")
    lines.append(f"**Group**: {_brief_field(ticket.group, 'name')}")
    lines.append(f"**Owner**: {_brief_field(ticket.owner, 'email')}")
    lines.append(f"**Customer**: {_brief_field(ticket.customer, 'email')}")
    lines.append(f"**Created**: {ticket.created_at.isoformat()}")
    lines.append(f"**Updated**: {ticket.updated_at.isoformat()}")
    lines.append("")

    # Tags
    if hasattr(ticket, "tags") and ticket.tags:
        lines.append(f"**Tags**: {', '.join(ticket.tags)}")
        lines.append("")

    # Articles
    if hasattr(ticket, "articles") and ticket.articles:
        lines.extend(_format_ticket_articles_section(ticket.articles))

    return "\n".join(lines)


def _format_user_contact_section(user: User) -> list[str]:
    """Build contact information section for user markdown."""
    fields = []
    for attr, label in [("phone", "Phone"), ("mobile", "Mobile"), ("fax", "Fax"), ("web", "Web")]:
        if value := getattr(user, attr, None):
            fields.append(f"- **{label}**: {value}")
    return ["## Contact Information", "", *fields, ""] if fields else []


def _format_user_address_section(user: User) -> list[str]:
    """Build address section for user markdown."""
    fields = []
    if user.department:
        fields.append(f"- **Department**: {user.department}")
    if user.street:
        fields.append(f"- **Street**: {user.street}")
    if user.city or user.zip:
        city_zip = f"{user.city or ''} {user.zip or ''}".strip()
        fields.append(f"- **City/Zip**: {city_zip}")
    if user.country:
        fields.append(f"- **Country**: {user.country}")
    if user.address:
        fields.append(f"- **Address**: {user.address}")
    return ["## Address", "", *fields, ""] if fields else []


def _format_user_ooo_section(user: User) -> list[str]:
    """Build out-of-office section for user markdown."""
    if not user.out_of_office:
        return []

    lines = ["## Out of Office", "", "- **Status**: Active"]
    if user.out_of_office_start_at:
        lines.append(f"- **Start**: {user.out_of_office_start_at.isoformat()}")
    if user.out_of_office_end_at:
        lines.append(f"- **End**: {user.out_of_office_end_at.isoformat()}")
    if user.out_of_office_replacement_id:
        lines.append(f"- **Replacement ID**: {user.out_of_office_replacement_id}")
    lines.append("")
    return lines


def _format_user_metadata_section(user: User) -> list[str]:
    """Build metadata section for user markdown."""
    lines = ["## Metadata", "", f"- **Created**: {user.created_at.isoformat()}"]
    lines.append(f"- **Updated**: {user.updated_at.isoformat()}")
    if user.last_login:
        lines.append(f"- **Last Login**: {user.last_login.isoformat()}")
    return lines


def _format_user_detail_markdown(user: User) -> str:
    """Format single user with full details as markdown.

    Args:
        user: User object to format

    Returns:
        Markdown-formatted string
    """
    # Build full name and basic info
    name_parts = [p for p in [user.firstname, user.lastname] if p]
    full_name = " ".join(name_parts) if name_parts else "Unnamed User"

    lines = [f"# User: {full_name}", "", f"**ID**: {user.id}", f"**Login**: {user.login or 'N/A'}"]
    lines.append(f"**Email**: {user.email or 'N/A'}")
    lines.append(f"**Active**: {user.active}")
    if user.vip:
        lines.append(f"**VIP**: {user.vip}")
    if user.verified:
        lines.append(f"**Verified**: {user.verified}")
    lines.append("")

    # Organization
    if user.organization:
        lines.extend([f"**Organization**: {_brief_field(user.organization, 'name')}", ""])

    # Optional sections
    lines.extend(_format_user_contact_section(user))
    lines.extend(_format_user_address_section(user))
    lines.extend(_format_user_ooo_section(user))

    # Note
    if user.note:
        lines.extend(["## Notes", "", user.note, ""])

    lines.extend(_format_user_metadata_section(user))
    return "\n".join(lines)


def _format_org_domain_section(org: Organization) -> list[str]:
    """Build domain information section for organization markdown."""
    if not (org.domain or org.domain_assignment):
        return []

    lines = ["## Domain", ""]
    if org.domain:
        lines.append(f"- **Domain**: {org.domain}")
    lines.append(f"- **Domain Assignment**: {org.domain_assignment}")
    lines.append("")
    return lines


def _extract_member_info(member: dict | object) -> tuple[str, str]:
    """Extract name and email from member dict or UserBrief object."""
    if isinstance(member, dict):
        email = member.get("email", "Unknown")
        firstname = member.get("firstname", "")
        lastname = member.get("lastname", "")
    else:
        # UserBrief object
        email = getattr(member, "email", None) or "Unknown"
        firstname = getattr(member, "firstname", None) or ""
        lastname = getattr(member, "lastname", None) or ""

    name = f"{firstname} {lastname}".strip()
    return (name or email, email)


def _format_org_members_section(members: list) -> list[str]:
    """Build members section for organization markdown."""
    if not members:
        return []

    lines = ["## Members", ""]
    for member in members:
        name, email = _extract_member_info(member)
        lines.append(f"- {name} ({email})")
    lines.append("")
    return lines


def _format_org_metadata_section(org: Organization) -> list[str]:
    """Build metadata section for organization markdown."""
    return [
        "## Metadata",
        "",
        f"- **Created**: {org.created_at.isoformat()}",
        f"- **Updated**: {org.updated_at.isoformat()}",
    ]


def _format_organization_detail_markdown(org: Organization) -> str:
    """Format single organization with full details as markdown.

    Args:
        org: Organization object to format

    Returns:
        Markdown-formatted string
    """
    lines = [f"# Organization: {org.name}", ""]
    lines.append(f"**ID**: {org.id}")
    lines.append(f"**Active**: {org.active}")
    lines.append(f"**Shared**: {org.shared}")
    lines.append("")

    # Optional sections
    lines.extend(_format_org_domain_section(org))
    if hasattr(org, "members") and org.members:
        lines.extend(_format_org_members_section(org.members))

    # Note
    if org.note:
        lines.extend(["## Notes", "", org.note, ""])

    lines.extend(_format_org_metadata_section(org))
    return "\n".join(lines)


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
        self.mcp = FastMCP("zammad_mcp", lifespan=self._create_lifespan())
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

        @self.mcp.tool(annotations=_read_only_annotations("Search Tickets"))
        def zammad_search_tickets(params: TicketSearchParams) -> str:
            """Search for tickets with filters and pagination.

            Args:
                params (TicketSearchParams): Validated search parameters containing:
                    - query (str | None): Search string (matches title, body, tags)
                    - state (str | None): Filter by state name (e.g., "open", "closed")
                    - priority (str | None): Filter by priority name (e.g., "high")
                    - group (str | None): Filter by group name
                    - owner (str | None): Filter by owner email/login
                    - customer (str | None): Filter by customer email/login
                    - page (int): Page number (default: 1)
                    - per_page (int): Results per page, 1-100 (default: 25)
                    - response_format (ResponseFormat): Output format (default: MARKDOWN)

            Returns:
                str: Formatted response with the following schema:

                Markdown format (default):
                ```
                # Ticket Search Results: [filters]

                Found N ticket(s)

                ## Ticket #65003 - Title
                - **ID**: 123 (use this for get_ticket, NOT number)
                - **State**: open
                - **Priority**: high
                - **Created**: 2024-01-15T10:30:00Z
                ```

                JSON format:
                ```json
                {
                    "items": [
                        {
                            "id": 123,
                            "number": "65003",
                            "title": "string",
                            "state": {"id": 1, "name": "open"},
                            "priority": {"id": 2, "name": "high"},
                            "created_at": "2024-01-15T10:30:00Z"
                        }
                    ],
                    "total": null,
                    "count": 20,
                    "page": 1,
                    "per_page": 20,
                    "has_more": true,
                    "next_page": 2,
                    "next_offset": 20
                }
                ```

            Examples:
                - Use when: "Find all open tickets" -> state="open"
                - Use when: "Search for network issues" -> query="network"
                - Use when: "Tickets assigned to sarah" -> owner="sarah@company.com"
                - Don't use when: You have ticket ID (use zammad_get_ticket instead)

            Error Handling:
                - Returns "Found 0 ticket(s)" if no matches
                - May be truncated if results exceed 25,000 characters (use pagination)

            Note:
                Use the 'id' field from results for get_ticket, NOT the 'number' field.
                Example: Ticket #65003 may have id=123. Use id=123 for API calls.
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

        @self.mcp.tool(annotations=_read_only_annotations("Get Ticket Details"))
        def zammad_get_ticket(params: GetTicketParams) -> str:
            """Get detailed information about a specific ticket by ID.

            Parameters:
                ticket_id (int): Internal database ID (required, must be > 0).
                    NOTE: This is the 'id' field from search results, NOT the display 'number'.
                include_articles (bool): Include ticket articles/comments (default: True)
                article_limit (int): Maximum articles to return (default: 10, use -1 for all)
                article_offset (int): Articles to skip for pagination (default: 0)
                response_format (ResponseFormat): Output format (default: MARKDOWN)

            Returns:
                str: Ticket details in markdown (default) or JSON format with fields:
                    id, number, title, state, priority, group, owner, customer,
                    created_at, updated_at, articles (if include_articles=True)

            Examples:
                - Use when: "Get details for ticket 123" -> ticket_id=123
                - Use when: "Show ticket with articles" -> ticket_id=123, include_articles=True
                - Don't use when: Searching by criteria (use zammad_search_tickets)
                - Don't use when: Only have ticket number (search first to get ID)

            Note:
                ticket_id must be the internal database ID from the 'id' field in search
                results, NOT the display number. Example: Ticket #65003 may have id=123;
                use id=123 for this tool.
            """
            client = self.get_client()
            try:
                ticket_data = client.get_ticket(
                    ticket_id=params.ticket_id,
                    include_articles=params.include_articles,
                    article_limit=params.article_limit,
                    article_offset=params.article_offset,
                )
                ticket = Ticket(**ticket_data)

                # Format response based on preference
                if params.response_format == ResponseFormat.JSON:
                    result = json.dumps(ticket.model_dump(), indent=2, default=str)
                else:  # MARKDOWN (default)
                    result = _format_ticket_detail_markdown(ticket)

                return truncate_response(result)
            except Exception as e:
                _handle_ticket_not_found_error(params.ticket_id, e)

        @self.mcp.tool(annotations=_write_annotations("Create New Ticket"))
        def zammad_create_ticket(params: TicketCreate) -> Ticket:
            """Create a new ticket in Zammad with initial article.

            Args:
                params (TicketCreate): Validated ticket creation parameters containing:
                    - title (str): Ticket title/subject (required)
                    - group (str): Group name to assign ticket (required)
                    - customer (str): Customer email or login (required)
                    - article (dict): Initial article with body and type (required)
                    - state (str | None): State name (default: "new")
                    - priority (str | None): Priority name (default: "2 normal")
                    - owner (str | None): Owner email or login
                    - tags (list[str] | None): Initial tags

            Returns:
                Ticket: The created ticket object with schema:

                ```json
                {
                    "id": 124,
                    "number": "65004",
                    "title": "New issue",
                    "state": {"id": 1, "name": "new"},
                    "priority": {"id": 2, "name": "2 normal"},
                    "customer": {"id": 5, "email": "user@example.com"},
                    "group": {"id": 3, "name": "Support"},
                    "created_at": "2024-01-15T15:00:00Z"
                }
                ```

            Examples:
                - Use when: "Create ticket for server outage" -> title, group, customer, article
                - Use when: "New high priority ticket" -> title, group, customer, article, priority="high"
                - Don't use when: Ticket already exists (use zammad_update_ticket)
                - Don't use when: Only adding comment to existing ticket (use zammad_add_article)

            Error Handling:
                - Returns "Error: Validation failed" if required fields missing
                - Returns "Error: Permission denied" if no create permissions
                - Returns "Error: Resource not found" if group/customer/state invalid
                - Validates group, customer, state, priority names before creation

            Note:
                The article parameter must include 'body' and 'type' (e.g., 'note', 'email').
                All name-based references (group, customer, state, priority) are validated.
                Created ticket returns with expanded field objects, not just IDs.
            """
            client = self.get_client()
            ticket_data = client.create_ticket(**params.model_dump(exclude_none=True, mode="json"))

            return Ticket(**ticket_data)

        @self.mcp.tool(annotations=_write_annotations("Update Ticket"))
        def zammad_update_ticket(params: TicketUpdateParams) -> Ticket:
            """Update an existing ticket's fields.

            Args:
                params (TicketUpdateParams): Validated update parameters containing:
                    - ticket_id (int): Internal database ID (required, NOT display number)
                    - title (str | None): New title
                    - state (str | None): New state name
                    - priority (str | None): New priority name
                    - group (str | None): New group name
                    - owner (str | None): New owner email/login
                    - customer (str | None): New customer email/login

            Returns:
                Ticket: The updated ticket object with schema:

                ```json
                {
                    "id": 123,
                    "number": "65003",
                    "title": "Updated title",
                    "state": {"id": 2, "name": "open"},
                    "priority": {"id": 3, "name": "high"},
                    "updated_at": "2024-01-15T16:00:00Z"
                }
                ```

            Examples:
                - Use when: "Change ticket 123 to high priority" -> ticket_id=123, priority="high"
                - Use when: "Close ticket 123" -> ticket_id=123, state="closed"
                - Use when: "Reassign ticket to Alice" -> ticket_id=123, owner="alice@company.com"
                - Don't use when: Adding comments (use zammad_add_article)
                - Don't use when: Adding tags (use zammad_add_ticket_tag)

            Error Handling:
                - Returns TicketIdGuidanceError if ticket not found (suggests using search)
                - Returns "Error: Permission denied" if no update permissions
                - Returns "Error: Validation failed" if field values invalid
                - Returns "Error: Resource not found" if group/owner/customer doesn't exist

            Note:
                ticket_id must be the internal database ID, NOT the display number.
                Use the 'id' field from search results, not the 'number' field.
                Example: Ticket #65003 may have id=123. Use id=123 for API calls.
                Only provided fields are updated; others remain unchanged (partial update).
            """
            client = self.get_client()
            try:
                # Extract ticket_id and update fields separately
                update_data = params.model_dump(exclude={"ticket_id"}, exclude_none=True)
                ticket_data = client.update_ticket(ticket_id=params.ticket_id, **update_data)
                return Ticket(**ticket_data)
            except Exception as e:
                _handle_ticket_not_found_error(params.ticket_id, e)

        @self.mcp.tool(annotations=_write_annotations("Add Ticket Article"))
        def zammad_add_article(params: ArticleCreate) -> Article:
            """Add an article (comment/note/email) to an existing ticket.

            Args:
                params (ArticleCreate): Validated article creation parameters containing:
                    - ticket_id (int): Internal database ID (required, NOT display number)
                    - body (str): Article content/message (required)
                    - article_type (ArticleType): Type enum - NOTE, EMAIL, etc. (required)
                    - internal (bool): Internal note vs customer-visible (default: False)
                    - subject (str | None): Article subject (for emails)
                    - content_type (str | None): text/plain or text/html (default: text/plain)
                    - to (str | None): Email recipient (for email type)
                    - cc (str | None): Email CC recipients

            Returns:
                Article: The created article object with schema:

                ```json
                {
                    "id": 456,
                    "ticket_id": 123,
                    "body": "Article content",
                    "type": "note",
                    "internal": false,
                    "created_at": "2024-01-15T16:30:00Z",
                    "created_by": {"id": 2, "email": "agent@company.com"}
                }
                ```

            Examples:
                - Use when: "Add note to ticket 123" -> ticket_id=123, body="text", article_type=NOTE
                - Use when: "Reply to customer" -> ticket_id=123, body="reply", article_type=EMAIL
                - Use when: "Internal comment" -> ticket_id=123, body="note", article_type=NOTE, internal=True
                - Don't use when: Creating new ticket (use zammad_create_ticket with article)
                - Don't use when: Updating ticket fields (use zammad_update_ticket)

            Error Handling:
                - Returns "Error: Validation failed" if body or type missing
                - Returns "Error: Resource not found" if ticket_id invalid
                - Returns "Error: Permission denied" if no article create permissions
                - Sanitizes HTML content if content_type is text/html

            Note:
                ticket_id must be the internal database ID, NOT the display number.
                Use the 'id' field from search results, not the 'number' field.
                Example: Ticket #65003 may have id=123. Use id=123 for API calls.
                Internal articles are only visible to agents, not customers.
            """
            client = self.get_client()
            # Extract ticket_id and article_type separately to avoid duplicate kwargs
            # Use mode="json" to convert enums to strings, by_alias=True for API compatibility
            article_params = params.model_dump(mode="json", by_alias=True, exclude={"ticket_id", "article_type"})
            article_data = client.add_article(
                ticket_id=params.ticket_id, article_type=params.article_type.value, **article_params
            )

            return Article(**article_data)

        @self.mcp.tool(annotations=_read_only_annotations("Get Article Attachments"))
        def zammad_get_article_attachments(params: GetArticleAttachmentsParams) -> list[Attachment]:
            """Get list of attachments for a specific article in a ticket.

            Args:
                params (GetArticleAttachmentsParams): Validated parameters containing:
                    - ticket_id (int): Internal database ID (required, NOT display number)
                    - article_id (int): Article ID within the ticket (required)

            Returns:
                list[Attachment]: List of attachment metadata objects with schema:

                ```json
                [
                    {
                        "id": 789,
                        "filename": "screenshot.png",
                        "size": "245678",
                        "preferences": {
                            "Content-Type": "image/png"
                        }
                    }
                ]
                ```

            Examples:
                - Use when: "List attachments for article 456 in ticket 123" -> ticket_id=123, article_id=456
                - Use when: "Check if article has attachments" -> ticket_id=123, article_id=456
                - Don't use when: Downloading attachment content (use zammad_download_attachment)
                - Don't use when: Article ID unknown (use zammad_get_ticket with include_articles first)

            Error Handling:
                - Returns empty list if article has no attachments
                - Returns "Error: Resource not found" if ticket_id or article_id invalid
                - Returns "Error: Permission denied" if no access to ticket/article

            Note:
                ticket_id must be the internal database ID, NOT the display number.
                Use the 'id' field from search results, not the 'number' field.
                Example: Ticket #65003 may have id=123. Use id=123 for API calls.
                Returns metadata only; use zammad_download_attachment to get file content.
            """
            client = self.get_client()
            attachments_data = client.get_article_attachments(params.ticket_id, params.article_id)
            return [Attachment(**attachment) for attachment in attachments_data]

        @self.mcp.tool(annotations=_read_only_annotations("Download Attachment"))
        def zammad_download_attachment(params: DownloadAttachmentParams) -> str:
            """Download attachment file content from a ticket article.

            Args:
                params (DownloadAttachmentParams): Validated parameters containing:
                    - ticket_id (int): Internal database ID (required, NOT display number)
                    - article_id (int): Article ID containing attachment (required)
                    - attachment_id (int): Attachment ID to download (required)
                    - max_bytes (int | None): Maximum file size limit (default: None)

            Returns:
                str: Base64-encoded binary content of the attachment file.
                     Decode using base64.b64decode() to get original bytes.

            Examples:
                - Use when: "Download attachment 789 from article 456" -> ticket_id=123, article_id=456, attachment_id=789
                - Use when: "Get file with size limit" -> ticket_id=123, article_id=456, attachment_id=789, max_bytes=1000000
                - Don't use when: Only need attachment metadata (use zammad_get_article_attachments)
                - Don't use when: Attachment IDs unknown (list attachments first)

            Error Handling:
                - Raises AttachmentDownloadError if download fails
                - Raises AttachmentDownloadError if file exceeds max_bytes limit
                - Returns "Error: Resource not found" if ticket_id/article_id/attachment_id invalid
                - Returns "Error: Permission denied" if no access to attachment

            Note:
                ticket_id must be the internal database ID, NOT the display number.
                Use the 'id' field from search results, not the 'number' field.
                Example: Ticket #65003 may have id=123. Use id=123 for API calls.
                Large attachments may exceed token limits; use max_bytes to prevent issues.
                Returns base64-encoded string for safe transmission of binary data.
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

        @self.mcp.tool(annotations=_idempotent_write_annotations("Add Ticket Tag"))
        def zammad_add_ticket_tag(params: TagOperationParams) -> TagOperationResult:
            """Add a tag to a ticket (idempotent operation).

            Args:
                params (TagOperationParams): Validated parameters containing:
                    - ticket_id (int): Internal database ID (required, NOT display number)
                    - tag (str): Tag name to add (required)

            Returns:
                TagOperationResult: Operation result with schema:

                ```json
                {
                    "success": true
                }
                ```

            Examples:
                - Use when: "Tag ticket 123 as urgent" -> ticket_id=123, tag="urgent"
                - Use when: "Add follow-up tag" -> ticket_id=123, tag="follow-up"
                - Don't use when: Removing tags (use zammad_remove_ticket_tag)
                - Don't use when: Setting ticket priority/state (use zammad_update_ticket)

            Error Handling:
                - Returns success=true even if tag already exists (idempotent)
                - Returns "Error: Resource not found" if ticket_id invalid
                - Returns "Error: Permission denied" if no tagging permissions

            Note:
                ticket_id must be the internal database ID, NOT the display number.
                Use the 'id' field from search results, not the 'number' field.
                Example: Ticket #65003 may have id=123. Use id=123 for API calls.
                This operation is idempotent - adding same tag twice succeeds both times.
            """
            client = self.get_client()
            result = client.add_ticket_tag(params.ticket_id, params.tag)
            return TagOperationResult(**result)

        @self.mcp.tool(annotations=_idempotent_write_annotations("Remove Ticket Tag"))
        def zammad_remove_ticket_tag(params: TagOperationParams) -> TagOperationResult:
            """Remove a tag from a ticket (idempotent operation).

            Args:
                params (TagOperationParams): Validated parameters containing:
                    - ticket_id (int): Internal database ID (required, NOT display number)
                    - tag (str): Tag name to remove (required)

            Returns:
                TagOperationResult: Operation result with schema:

                ```json
                {
                    "success": true
                }
                ```

            Examples:
                - Use when: "Remove urgent tag from ticket 123" -> ticket_id=123, tag="urgent"
                - Use when: "Untag ticket" -> ticket_id=123, tag="follow-up"
                - Don't use when: Adding tags (use zammad_add_ticket_tag)
                - Don't use when: Changing ticket priority/state (use zammad_update_ticket)

            Error Handling:
                - Returns success=true even if tag doesn't exist (idempotent)
                - Returns "Error: Resource not found" if ticket_id invalid
                - Returns "Error: Permission denied" if no tagging permissions

            Note:
                ticket_id must be the internal database ID, NOT the display number.
                Use the 'id' field from search results, not the 'number' field.
                Example: Ticket #65003 may have id=123. Use id=123 for API calls.
                This operation is idempotent - removing non-existent tag succeeds.
            """
            client = self.get_client()
            result = client.remove_ticket_tag(params.ticket_id, params.tag)
            return TagOperationResult(**result)

    def _setup_user_org_tools(self) -> None:
        """Register user and organization tools."""

        @self.mcp.tool(annotations=_read_only_annotations("Get User Details"))
        def zammad_get_user(params: GetUserParams) -> str:
            """Get detailed information about a specific user by ID.

            Parameters:
                user_id (int): User's internal database ID (required, must be > 0)
                response_format (ResponseFormat): Output format (default: MARKDOWN)

            Returns:
                str: User details in markdown (default) or JSON format with fields:
                    id, login, firstname, lastname, email, organization, active, vip,
                    phone, mobile, fax, web, department, street, city, zip, country,
                    address, out_of_office, out_of_office_start_at, out_of_office_end_at,
                    out_of_office_replacement_id, note, created_at, updated_at, last_login

            Examples:
                - Use when: "Get details for user 5" -> user_id=5
                - Don't use when: Searching by email/name (use zammad_search_users)
                - Don't use when: Getting current user (use zammad_get_current_user)

            Note:
                Returns full user profile including organization, roles, and preferences.
            """
            client = self.get_client()
            user_data = client.get_user(params.user_id)
            user = User(**user_data)

            # Format response based on preference
            if params.response_format == ResponseFormat.JSON:
                result = json.dumps(user.model_dump(), indent=2, default=str)
            else:  # MARKDOWN (default)
                result = _format_user_detail_markdown(user)

            return truncate_response(result)

        @self.mcp.tool(annotations=_read_only_annotations("Search Users"))
        def zammad_search_users(params: SearchUsersParams) -> str:
            """Search for users by query string with pagination.

            Args:
                params (SearchUsersParams): Validated search parameters containing:
                    - query (str): Search string (matches name, email, login) (required)
                    - page (int): Page number (default: 1)
                    - per_page (int): Results per page, 1-100 (default: 25)
                    - response_format (ResponseFormat): Output format (default: MARKDOWN)

            Returns:
                str: Formatted response with the following schema:

                Markdown format (default):
                ```
                # User Search Results: query='search term'

                Found N user(s)

                ## Jane Doe
                - **ID**: 5
                - **Email**: jane@example.com
                - **Login**: jane@example.com
                - **Active**: true
                ```

                JSON format:
                ```json
                {
                    "items": [
                        {
                            "id": 5,
                            "login": "jane@example.com",
                            "firstname": "Jane",
                            "lastname": "Doe",
                            "email": "jane@example.com",
                            "active": true
                        }
                    ],
                    "total": null,
                    "count": 10,
                    "page": 1,
                    "per_page": 25,
                    "has_more": false,
                    "next_page": null
                }
                ```

            Examples:
                - Use when: "Find user Sarah" -> query="Sarah"
                - Use when: "Search by email" -> query="user@example.com"
                - Use when: "List users in organization" -> query="@acme.com"
                - Don't use when: You have user ID (use zammad_get_user instead)

            Error Handling:
                - Returns "Found 0 user(s)" if no matches
                - May be truncated if results exceed 25,000 characters (use pagination)

            Note:
                Use the 'id' field from results for zammad_get_user calls.
                Search matches firstname, lastname, email, and login fields.
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

        @self.mcp.tool(annotations=_read_only_annotations("Get Organization Details"))
        def zammad_get_organization(params: GetOrganizationParams) -> str:
            """Get detailed information about a specific organization by ID.

            Args:
                params (GetOrganizationParams): Validated parameters containing:
                    - org_id (int): Organization's internal database ID (required)
                    - response_format (ResponseFormat): Output format - markdown (default) or json

            Returns:
                str: Formatted organization information.
                     - Markdown format: Human-readable with sections for domain, members, notes
                     - JSON format: Complete organization object with all fields

                Example JSON response:
                ```json
                {
                    "id": 2,
                    "name": "ACME Corp",
                    "domain": "acme.com",
                    "active": true,
                    "note": "VIP customer",
                    "created_at": "2022-05-10T12:00:00Z"
                }
                ```

            Examples:
                - Use when: "Get details for organization 2" -> org_id=2
                - Use when: "Show organization info" -> org_id=2
                - Don't use when: Searching by name (use zammad_search_organizations)
                - Don't use when: Getting user's organization (included in zammad_get_user)

            Error Handling:
                - Returns "Error: Resource not found" if org_id doesn't exist
                - Returns "Error: Permission denied" if no access to organization data
                - Returns "Error: Invalid authentication" on 401 status

            Note:
                Returns full organization profile including custom fields.
                Use zammad_search_organizations if you need to find by name.
            """
            client = self.get_client()
            org_data = client.get_organization(params.org_id)
            org = Organization(**org_data)

            # Format response based on preference
            if params.response_format == ResponseFormat.JSON:
                result = json.dumps(org.model_dump(), indent=2, default=str)
            else:  # MARKDOWN (default)
                result = _format_organization_detail_markdown(org)

            return truncate_response(result)

        @self.mcp.tool(annotations=_read_only_annotations("Search Organizations"))
        def zammad_search_organizations(params: SearchOrganizationsParams) -> str:
            """Search for organizations by query string with pagination.

            Args:
                params (SearchOrganizationsParams): Validated search parameters containing:
                    - query (str): Search string (matches name, domain, note) (required)
                    - page (int): Page number (default: 1)
                    - per_page (int): Results per page, 1-100 (default: 25)
                    - response_format (ResponseFormat): Output format (default: MARKDOWN)

            Returns:
                str: Formatted response with the following schema:

                Markdown format (default):
                ```
                # Organization Search Results: query='search term'

                Found N organization(s)

                ## ACME Corp
                - **ID**: 2
                - **Active**: true
                ```

                JSON format:
                ```json
                {
                    "items": [
                        {
                            "id": 2,
                            "name": "ACME Corp",
                            "domain": "acme.com",
                            "active": true
                        }
                    ],
                    "total": null,
                    "count": 5,
                    "page": 1,
                    "per_page": 25,
                    "has_more": false,
                    "next_page": null
                }
                ```

            Examples:
                - Use when: "Find organization ACME" -> query="ACME"
                - Use when: "Search by domain" -> query="acme.com"
                - Use when: "Find VIP organizations" -> query="VIP"
                - Don't use when: You have org ID (use zammad_get_organization instead)

            Error Handling:
                - Returns "Found 0 organization(s)" if no matches
                - May be truncated if results exceed 25,000 characters (use pagination)

            Note:
                Use the 'id' field from results for zammad_get_organization calls.
                Search matches name, domain, and note fields.
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

        @self.mcp.tool(annotations=_read_only_annotations("Get Current User"))
        def zammad_get_current_user() -> User:
            """Get information about the currently authenticated user.

            Args:
                None (uses authentication token from environment)

            Returns:
                User: Complete user object for authenticated user with schema:

                ```json
                {
                    "id": 2,
                    "login": "agent@company.com",
                    "firstname": "Agent",
                    "lastname": "Smith",
                    "email": "agent@company.com",
                    "organization": {"id": 1, "name": "Internal"},
                    "active": true,
                    "roles": ["Agent", "Admin"],
                    "created_at": "2022-01-01T00:00:00Z"
                }
                ```

            Examples:
                - Use when: "Who am I?" -> no parameters needed
                - Use when: "Show my user info" -> no parameters needed
                - Use when: "What are my permissions?" -> check roles in response
                - Don't use when: Getting other users (use zammad_get_user or zammad_search_users)

            Error Handling:
                - Returns "Error: Invalid authentication" if token invalid/expired
                - Returns "Error: Permission denied" if token lacks user access

            Note:
                This is useful for checking authentication status and current user permissions.
                Uses ZAMMAD_HTTP_TOKEN from environment for authentication.
                Returns expanded user object including roles and organization.
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

        @self.mcp.tool(annotations=_read_only_annotations("Get Ticket Statistics"))
        def zammad_get_ticket_stats(params: GetTicketStatsParams) -> TicketStats:
            """Get aggregated ticket statistics with counts by state.

            Args:
                params (GetTicketStatsParams): Validated parameters containing:
                    - group (str | None): Filter by group name
                    - start_date (datetime | None): Start date filter (not yet implemented)
                    - end_date (datetime | None): End date filter (not yet implemented)

            Returns:
                TicketStats: Statistics object with schema:

                ```json
                {
                    "total_count": 1523,
                    "open_count": 245,
                    "closed_count": 1200,
                    "pending_count": 78,
                    "escalated_count": 12,
                    "avg_first_response_time": null,
                    "avg_resolution_time": null
                }
                ```

            Examples:
                - Use when: "Show ticket statistics" -> no parameters
                - Use when: "Stats for Support group" -> group="Support"
                - Use when: "How many escalated tickets?" -> check escalated_count
                - Don't use when: Need individual ticket details (use zammad_search_tickets)
                - Don't use when: Need real-time counts (this scans all tickets via pagination)

            Error Handling:
                - Returns counts with warning if max page limit reached (1000 pages)
                - Returns "Error: Resource not found" if group name invalid
                - Returns "Error: Permission denied" if no access to tickets

            Note:
                Uses pagination to scan tickets without loading all into memory.
                May take several seconds for large ticket databases (>10k tickets).
                State categorization uses state_type_id: new/open=open, closed=closed, pending=pending.
                Date filtering (start_date, end_date) not yet implemented - shows warning if provided.
                Processes up to 100,000 tickets (1000 pages x 100 per page).
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

        @self.mcp.tool(annotations=_read_only_annotations("List Groups"))
        def zammad_list_groups(params: ListParams) -> str:
            """Get complete list of all available groups (cached).

            Args:
                params (ListParams): Validated parameters containing:
                    - response_format (ResponseFormat): Output format (default: MARKDOWN)

            Returns:
                str: Formatted response with the following schema:

                Markdown format (default):
                ```
                # Group List

                Found N group(s)

                - **Support** (ID: 1)
                - **Sales** (ID: 2)
                - **Technical** (ID: 3)
                ```

                JSON format:
                ```json
                {
                    "items": [
                        {"id": 1, "name": "Support"},
                        {"id": 2, "name": "Sales"}
                    ],
                    "total": 2,
                    "count": 2,
                    "page": 1,
                    "per_page": 2,
                    "has_more": false
                }
                ```

            Examples:
                - Use when: "List all groups" -> no search parameters
                - Use when: "What groups exist?" -> check available groups
                - Use when: "Show group names for ticket creation" -> get valid group names
                - Don't use when: Searching specific groups (groups are cached, just list all)

            Error Handling:
                - Returns empty list if no groups configured (unusual)
                - Returns "Error: Permission denied" if no group access
                - Returns "Error: Invalid authentication" on 401 status

            Note:
                Results are cached in memory for performance (cleared on server restart).
                All groups are returned in a single response (no pagination needed).
                Use group 'name' field when creating/updating tickets, not ID.
            """
            groups = self._get_cached_groups()

            # Format response
            if params.response_format == ResponseFormat.JSON:
                result = _format_list_json(groups)
            else:
                result = _format_list_markdown(groups, "Group")

            return truncate_response(result)

        @self.mcp.tool(annotations=_read_only_annotations("List Ticket States"))
        def zammad_list_ticket_states(params: ListParams) -> str:
            """Get complete list of all available ticket states (cached).

            Args:
                params (ListParams): Validated parameters containing:
                    - response_format (ResponseFormat): Output format (default: MARKDOWN)

            Returns:
                str: Formatted response with the following schema:

                Markdown format (default):
                ```
                # Ticket State List

                Found N ticket state(s)

                - **new** (ID: 1)
                - **open** (ID: 2)
                - **closed** (ID: 3)
                - **pending reminder** (ID: 4)
                ```

                JSON format:
                ```json
                {
                    "items": [
                        {"id": 1, "name": "new", "state_type_id": 1},
                        {"id": 2, "name": "open", "state_type_id": 2},
                        {"id": 3, "name": "closed", "state_type_id": 3}
                    ],
                    "total": 3,
                    "count": 3,
                    "page": 1,
                    "per_page": 3,
                    "has_more": false
                }
                ```

            Examples:
                - Use when: "List all ticket states" -> no search parameters
                - Use when: "What states can I use?" -> get valid state names
                - Use when: "Show state options for ticket update" -> get available states
                - Don't use when: Searching specific states (states are cached, just list all)

            Error Handling:
                - Returns empty list if no states configured (should never happen)
                - Returns "Error: Permission denied" if no state access
                - Returns "Error: Invalid authentication" on 401 status

            Note:
                Results are cached in memory for performance (cleared on server restart).
                All states are returned in a single response (no pagination needed).
                Use state 'name' field when creating/updating tickets, not ID.
                State types: 1=new, 2=open, 3=closed, 4=pending reminder, 5=pending close.
            """
            states = self._get_cached_states()

            # Format response
            if params.response_format == ResponseFormat.JSON:
                result = _format_list_json(states)
            else:
                result = _format_list_markdown(states, "Ticket State")

            return truncate_response(result)

        @self.mcp.tool(annotations=_read_only_annotations("List Ticket Priorities"))
        def zammad_list_ticket_priorities(params: ListParams) -> str:
            """Get complete list of all available ticket priorities (cached).

            Args:
                params (ListParams): Validated parameters containing:
                    - response_format (ResponseFormat): Output format (default: MARKDOWN)

            Returns:
                str: Formatted response with the following schema:

                Markdown format (default):
                ```
                # Ticket Priority List

                Found N ticket priority/priorities

                - **1 low** (ID: 1)
                - **2 normal** (ID: 2)
                - **3 high** (ID: 3)
                ```

                JSON format:
                ```json
                {
                    "items": [
                        {"id": 1, "name": "1 low"},
                        {"id": 2, "name": "2 normal"},
                        {"id": 3, "name": "3 high"}
                    ],
                    "total": 3,
                    "count": 3,
                    "page": 1,
                    "per_page": 3,
                    "has_more": false
                }
                ```

            Examples:
                - Use when: "List all priorities" -> no search parameters
                - Use when: "What priorities exist?" -> get valid priority names
                - Use when: "Show priority options for ticket" -> get available priorities
                - Don't use when: Searching specific priorities (priorities are cached, just list all)

            Error Handling:
                - Returns empty list if no priorities configured (should never happen)
                - Returns "Error: Permission denied" if no priority access
                - Returns "Error: Invalid authentication" on 401 status

            Note:
                Results are cached in memory for performance (cleared on server restart).
                All priorities are returned in a single response (no pagination needed).
                Use priority 'name' field when creating/updating tickets, not ID.
                Priority names typically include numbers for sorting (e.g., "1 low", "2 normal", "3 high").
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
