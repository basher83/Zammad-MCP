"""Zammad MCP Server implementation."""

import base64
import html
import json
import logging
import os
import re
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any, NoReturn, Protocol, TextIO, TypeVar

import requests  # type: ignore[import-untyped]
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token
from mcp.types import ToolAnnotations
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from .audit import AuditConfig, AuditLogger, error_details
from .audit_middleware import AuditMiddleware
from .client import ZammadClient
from .config import AuthConfig, TransportType
from .events import EventStore, ListEventsParams, ListEventsResult, WebhookEvent
from .logging_config import configure_logging
from .models import (
    Article,
    ArticleCreate,
    Attachment,
    AttachmentDownloadError,
    BulkTicketUpdateParams,
    BulkUpdateFailure,
    BulkUpdateResult,
    DownloadAttachmentParams,
    GetArticleAttachmentsParams,
    GetKBAnswerParams,
    GetKBCategoryParams,
    GetKnowledgeBaseParams,
    GetOrganizationParams,
    GetTicketParams,
    GetTicketStatsParams,
    GetTicketTagsParams,
    GetUserParams,
    Group,
    ListKBAnswersParams,
    ListKnowledgeBasesParams,
    ListParams,
    Organization,
    PriorityBrief,
    ResponseFormat,
    SearchKBAnswersParams,
    SearchOrganizationsParams,
    SearchUsersParams,
    StateBrief,
    TagOperationParams,
    TagOperationResult,
    Ticket,
    TicketCreate,
    TicketExportParams,
    TicketIdGuidanceError,
    TicketMergeParams,
    TicketMergeResult,
    TicketPriority,
    TicketSearchParams,
    TicketState,
    TicketStats,
    TicketUpdateParams,
    User,
    UserBrief,
    UserCreate,
)
from .resilience import CircuitOpenError, RetryExhaustedError
from .tool_params import flat_params
from .webhooks import WebhookHandler


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
QUEUE_PAGE_SIZE = 50

# Zammad state type IDs. These are seeded and fixed by Zammad (see
# db/seeds/ticket_state_types.rb): create_if_not_exists with explicit ids, so
# the built-in values are stable across versions and installations.
STATE_TYPE_NEW = 1
STATE_TYPE_OPEN = 2
STATE_TYPE_PENDING_REMINDER = 3
STATE_TYPE_PENDING_ACTION = 4
STATE_TYPE_CLOSED = 5
STATE_TYPE_MERGED = 6
MAX_PER_PAGE = 100  # Maximum results per page for pagination
# Zammad's search endpoint is backed by Elasticsearch, whose index.max_result_window
# defaults to 10,000. Past that the endpoint returns empty pages rather than an error,
# so an unguarded scan silently stops and under-reports.
SEARCH_RESULT_CAP = 10000
CHARACTER_LIMIT = 25000  # Maximum response size per MCP best practices
ARTICLE_BODY_TRUNCATE_LENGTH = 500  # Maximum length for article body in markdown formatting
MAX_EXPORT_ERRORS_LOGGED = 100  # Maximum number of per-ticket errors to log during export


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


def _destructive_write_annotations(title: str) -> ToolAnnotations:
    """Create destructive write tool annotations with title."""
    return ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
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


def _strip_html_tags(text: str) -> str:
    """Strip HTML tags and unescape HTML entities from text.

    Args:
        text: HTML or plain text string

    Returns:
        Plain text with HTML tags removed and entities decoded
    """
    clean = re.sub(r"<[^>]+>", "", text)
    return html.unescape(clean).strip()


def _escape_article_body(article: Article) -> str:
    """Escape HTML in article bodies to prevent injection.

    Args:
        article: The article to get the body from

    Returns:
        HTML-escaped body if content type is HTML, otherwise raw body
    """
    ct = (getattr(article, "content_type", None) or "").lower()
    return html.escape(article.body) if "html" in ct else article.body


def _sanitize_inline_text(value: object) -> str:
    """Neutralize control characters and HTML in a value rendered inline in markdown.

    Attachment filenames originate from user uploads, so they may contain
    newlines, control characters, or HTML/Markdown metacharacters that could
    break out of the list item or inject markup. Strip non-printable characters
    and HTML-escape the rest.

    Args:
        value: The value to sanitize (coerced to str)

    Returns:
        A single-line, HTML-escaped representation safe for inline rendering
    """
    text = "".join(ch for ch in str(value) if ch.isprintable())
    return html.escape(text, quote=False)


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

    # Attempt to shrink the "items" array if present
    if "items" in obj and isinstance(obj["items"], list):
        original_items = obj["items"]
        max_items = _find_max_items_for_limit(obj, original_items, limit, use_compact=use_compact)
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
        json_str = _serialize_json(obj, use_compact=use_compact)
        while obj["items"] and len(json_str) > limit:
            obj["items"].pop()
            json_str = _serialize_json(obj, use_compact=use_compact)

    return _serialize_json(obj, use_compact=use_compact)


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


def _format_custom_attribute_value(value: Any) -> str:
    """Render a custom attribute value for Markdown output."""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, default=str)
    return str(value)


def _format_custom_attributes_markdown(ticket: Ticket) -> list[str]:
    """Render custom object attributes retained on the ticket as a Markdown section.

    Args:
        ticket: Ticket whose extra (non-schema) fields are custom attributes.

    Returns:
        Markdown lines for the section, or an empty list when there are no custom attributes.
    """
    extras = ticket.model_extra or {}
    if not extras:
        return []
    lines = ["## Custom Attributes", ""]
    lines.extend(f"**{name}**: {_format_custom_attribute_value(value)}" for name, value in sorted(extras.items()))
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

    lines.extend(_format_custom_attributes_markdown(ticket))

    # Tags
    if hasattr(ticket, "tags") and ticket.tags:
        lines.append(f"**Tags**: {', '.join(ticket.tags)}")
        lines.append("")

    # Articles
    if hasattr(ticket, "articles") and ticket.articles:
        lines.append("## Articles")
        lines.append("")
        for i, article in enumerate(ticket.articles, 1):
            lines.append(f"### Article {i}")
            # Handle both Article objects and dicts for defensive coding
            if isinstance(article, dict):
                from_field = article.get("from", "Unknown")
                type_field = article.get("type", "Unknown")
                created_at = article.get("created_at", "Unknown")
                body = article.get("body", "")
                attachments = article.get("attachments")
            else:
                # Article object - use attribute access
                from_field = article.from_ or "Unknown"
                type_field = article.type
                created_at = article.created_at
                body = article.body
                attachments = article.attachments

            lines.append(f"- **From**: {from_field}")
            lines.append(f"- **Type**: {type_field}")
            lines.append(f"- **Created**: {created_at}")
            article_id = article.get("id") if isinstance(article, dict) else article.id
            lines.extend(_format_article_attachments(attachments, article_id))
            lines.append("")
            # Truncate very long bodies
            if len(body) > ARTICLE_BODY_TRUNCATE_LENGTH:
                body = body[:ARTICLE_BODY_TRUNCATE_LENGTH] + "...\n(truncated)"
            lines.append(body)
            lines.append("")

    return "\n".join(lines)


def _attachment_field(att: Attachment | dict, name: str) -> object:
    """Read a field from an attachment in either dict or model form."""
    return att.get(name) if isinstance(att, dict) else getattr(att, name, None)


def _format_attachment_size(size: object) -> str:
    """Render a trailing size suffix for genuine non-negative byte counts."""
    if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
        return f", {size} bytes"
    return ""


def _format_attachment_line(att: Attachment | dict) -> str:
    """Format a single attachment as a sanitized markdown bullet line."""
    filename = _attachment_field(att, "filename")
    safe_id = _sanitize_inline_text(_attachment_field(att, "id"))
    safe_filename = _sanitize_inline_text(filename) if filename is not None else "(unnamed)"
    size_str = _format_attachment_size(_attachment_field(att, "size"))
    return f"  - id={safe_id}: {safe_filename}{size_str}"


def _format_article_attachments(attachments: list[Attachment] | list[dict] | None, article_id: int) -> list[str]:
    """Render an article's attachment list as markdown lines.

    Surfaces attachment id/filename/size so the LLM knows files exist and can
    fetch their content via zammad_download_attachment.
    """
    if not attachments:
        return []

    safe_article_id = _sanitize_inline_text(article_id)
    lines = [f"- **Attachments** (download via zammad_download_attachment, article_id={safe_article_id}):"]
    lines.extend(_format_attachment_line(att) for att in attachments)
    return lines


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

    # Out of Office
    if user.out_of_office:
        lines.extend(["## Out of Office", "", "- **Status**: Active"])
        if user.out_of_office_start_at:
            lines.append(f"- **Start**: {user.out_of_office_start_at.isoformat()}")
        if user.out_of_office_end_at:
            lines.append(f"- **End**: {user.out_of_office_end_at.isoformat()}")
        if user.out_of_office_replacement_id:
            lines.append(f"- **Replacement ID**: {user.out_of_office_replacement_id}")
        lines.append("")

    # Note and Metadata
    if user.note:
        lines.extend(["## Notes", "", user.note, ""])

    lines.extend(["## Metadata", "", f"- **Created**: {user.created_at.isoformat()}"])
    lines.append(f"- **Updated**: {user.updated_at.isoformat()}")
    if user.last_login:
        lines.append(f"- **Last Login**: {user.last_login.isoformat()}")

    return "\n".join(lines)


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

    # Domain Information
    if org.domain or org.domain_assignment:
        lines.append("## Domain")
        lines.append("")
        if org.domain:
            lines.append(f"- **Domain**: {org.domain}")
        lines.append(f"- **Domain Assignment**: {org.domain_assignment}")
        lines.append("")

    # Members
    if hasattr(org, "members") and org.members:
        lines.append("## Members")
        lines.append("")
        for member in org.members:
            if isinstance(member, dict):
                email = member.get("email", "Unknown")
                name = f"{member.get('firstname', '')} {member.get('lastname', '')}".strip() or email
            else:
                # UserBrief object
                email = getattr(member, "email", None) or "Unknown"
                firstname = getattr(member, "firstname", None) or ""
                lastname = getattr(member, "lastname", None) or ""
                name = f"{firstname} {lastname}".strip() or email
            lines.append(f"- {name} ({email})")
        lines.append("")

    # Note
    if org.note:
        lines.append("## Notes")
        lines.append("")
        lines.append(org.note)
        lines.append("")

    # Metadata
    lines.append("## Metadata")
    lines.append("")
    lines.append(f"- **Created**: {org.created_at.isoformat()}")
    lines.append(f"- **Updated**: {org.updated_at.isoformat()}")

    return "\n".join(lines)


def _extract_expanded_field_name(value: object) -> str:
    """Extract name from an expanded field (dict or string)."""
    if isinstance(value, dict):
        return str(value.get("name", ""))
    return str(value) if value else ""


def _build_export_article(article: dict[str, Any]) -> dict[str, Any]:
    """Build a single export article record with HTML stripped."""
    body = article.get("body", "")
    content_type = (article.get("content_type") or "").lower()
    if "html" in content_type:
        body = _strip_html_tags(body)

    return {
        "sender": article.get("sender", "Unknown"),
        "type": article.get("type", "note"),
        "from": article.get("from", ""),
        "subject": article.get("subject", ""),
        "body": body,
        "internal": article.get("internal", False),
        "created_at": article.get("created_at", ""),
    }


def _resolve_export_path(output_path: str) -> Path:
    """Resolve and validate an export output path against the configured export directory.

    Export writes to the host filesystem, so the destination is confined to the directory
    named by ZAMMAD_EXPORT_DIR. The variable is required: without it the export tool is
    unavailable rather than defaulting to a writable location.

    Symlinks are resolved before the containment check, so a symlink inside the export
    directory cannot be used to escape it.

    Args:
        output_path: Requested output path, absolute or relative to the export directory.

    Returns:
        Path: The resolved, validated absolute path.

    Raises:
        ValueError: If ZAMMAD_EXPORT_DIR is unset, is not a directory, or the resolved
            path would fall outside it.
    """
    export_dir_raw = os.environ.get("ZAMMAD_EXPORT_DIR")
    if not export_dir_raw:
        raise ValueError(
            "Ticket export is disabled: ZAMMAD_EXPORT_DIR is not set. "
            "Set it to a directory the server may write exports into."
        )

    export_dir = Path(export_dir_raw).expanduser().resolve()
    if not export_dir.is_dir():
        raise ValueError(f"ZAMMAD_EXPORT_DIR does not exist or is not a directory: {export_dir}")

    candidate = Path(output_path).expanduser()
    resolved = (export_dir / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()

    if resolved != export_dir and export_dir not in resolved.parents:
        raise ValueError(
            f"Refusing to write outside the export directory. "
            f"Resolved path {resolved} is not contained in ZAMMAD_EXPORT_DIR {export_dir}."
        )

    return resolved


def _build_export_record(
    ticket_data: dict[str, Any],
    include_internal: bool,
    summary: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Build a JSONL export record from ticket data.

    The per-ticket detail fetch uses the Zammad ticket find endpoint, which does not
    support expansion, so group/state/priority arrive as numeric *_id fields only. The
    list and search endpoints do expand those names, so the batch summary the ticket
    came from is used as a fallback for the human-readable values.

    Args:
        ticket_data: Full ticket detail, including articles.
        include_internal: Whether internal articles are included in the conversation.
        summary: The batch entry this ticket came from, used to recover expanded names.
        tags: Tags fetched separately; the ticket payload never carries them.
    """
    conversation = []
    for article in ticket_data.get("articles", []):
        if not include_internal and article.get("internal", False):
            continue
        conversation.append(_build_export_article(article))

    summary = summary or {}

    def expanded(field: str) -> str:
        """Prefer the detail payload, falling back to the expanded batch summary."""
        value = _extract_expanded_field_name(ticket_data.get(field, ""))
        if value:
            return value
        return _extract_expanded_field_name(summary.get(field, ""))

    raw_tags = tags if tags is not None else ticket_data.get("tags")
    resolved_tags = raw_tags if isinstance(raw_tags, list) else []

    return {
        "ticket_id": ticket_data.get("id"),
        "ticket_number": str(ticket_data.get("number", "")),
        "title": ticket_data.get("title", ""),
        "group": expanded("group"),
        "state": expanded("state"),
        "priority": expanded("priority"),
        "tags": resolved_tags,
        "created_at": str(ticket_data.get("created_at", "")),
        "updated_at": str(ticket_data.get("updated_at", "")),
        "conversation": conversation,
    }


def _format_export_summary(
    params: "TicketExportParams",
    exported_count: int,
    error_count: int,
    errors: list[str],
    elapsed: float,
    use_search: bool,
    export_path: Path | None = None,
) -> str:
    """Format export summary as markdown."""
    lines = ["# Ticket Export Complete", ""]
    lines.append(f"- **File**: `{export_path if export_path is not None else params.output_path}`")
    lines.append(f"- **Tickets exported**: {exported_count}")
    lines.append(f"- **Errors**: {error_count}")
    lines.append(f"- **Elapsed time**: {elapsed:.1f}s")
    lines.append(f"- **Mode**: {'search (10K limit)' if use_search else 'list (no limit)'}")
    if params.resume_from_page > 1:
        lines.append(f"- **Resumed from page**: {params.resume_from_page}")
    lines.append("")

    if use_search:
        lines.append(
            "> **Note**: Filtered export uses the search endpoint, which is capped at 10,000 results by Zammad."
        )
        lines.append("")

    if errors:
        lines.append("## Errors (first 100)")
        lines.append("")
        for err in errors:
            lines.append(f"- {err}")

    return "\n".join(lines)


def _fetch_export_batch(
    client: "ZammadClient",
    params: "TicketExportParams",
    use_search: bool,
    page: int,
) -> list[dict[str, Any]]:
    """Fetch a batch of tickets for export using search or list endpoint."""
    if use_search:
        return client.search_tickets(
            query=params.query,
            group=params.group,
            state=params.state,
            created_after=params.created_after.isoformat() if params.created_after else None,
            created_before=params.created_before.isoformat() if params.created_before else None,
            page=page,
            per_page=params.per_page,
        )
    return client.list_tickets(page=page, per_page=params.per_page)


@dataclass
class _ExportProgress:
    """Running totals for a ticket export."""

    exported: int = 0
    error_count: int = 0
    errors: list[str] = field(default_factory=list)

    def record_error(self, ticket_id: Any, exc: Exception) -> None:
        """Count a per-ticket failure, keeping at most MAX_EXPORT_ERRORS_LOGGED messages.

        Args:
            ticket_id: ID of the ticket that failed.
            exc: The exception raised while exporting it.
        """
        self.error_count += 1
        if len(self.errors) < MAX_EXPORT_ERRORS_LOGGED:
            self.errors.append(f"Ticket {ticket_id}: {type(exc).__name__} - {exc}")

    def limit_reached(self, max_tickets: int | None) -> bool:
        """Return whether the optional max_tickets cap has been reached.

        Args:
            max_tickets: Optional. Export cap; None or 0 means unlimited.

        Returns:
            bool: True when the cap is set and met.
        """
        return bool(max_tickets and self.exported >= max_tickets)


def _iter_export_batches(
    client: "ZammadClient", params: "TicketExportParams", use_search: bool
) -> Iterator[list[dict[str, Any]]]:
    """Yield non-empty ticket batches from resume_from_page until the first empty page.

    The search endpoint is capped at MAX_PAGES_FOR_TICKET_SCAN pages, matching the
    ticket statistics scan; the list endpoint has no result cap, so list-mode
    exports page until Zammad returns nothing.

    Args:
        client: Zammad client used to fetch pages.
        params: Export parameters (filters, page size, resume page).
        use_search: Whether to use the search endpoint instead of the list endpoint.

    Returns:
        Iterator[list[dict[str, Any]]]: Batches in page order; stops at the first empty page.
    """
    last_page = MAX_PAGES_FOR_TICKET_SCAN if use_search else None
    page = params.resume_from_page
    while last_page is None or page <= last_page:
        batch = _fetch_export_batch(client, params, use_search, page)
        if not batch:
            return
        yield batch
        page += 1


def _fetch_export_record(
    client: "ZammadClient", params: "TicketExportParams", ticket_summary: dict[str, Any]
) -> dict[str, Any]:
    """Fetch one ticket's details (and optional tags) and build its export record.

    Args:
        client: Zammad client used for the detail and tag requests.
        params: Export parameters (delay, tag and internal-article options).
        ticket_summary: Batch entry for the ticket; must carry an ``id``.

    Returns:
        dict[str, Any]: The JSONL export record.
    """
    ticket_id = ticket_summary["id"]
    time.sleep(params.delay_seconds)
    ticket_data = client.get_ticket(ticket_id=ticket_id, include_articles=True, article_limit=-1)
    tags = client.get_ticket_tags(ticket_id) if params.include_tags else None
    return _build_export_record(ticket_data, params.include_internal_articles, summary=ticket_summary, tags=tags)


def _write_export_line(f: TextIO, record: dict[str, Any]) -> None:
    """Append one JSON record as a line and flush so progress survives crashes.

    Args:
        f: Open text file in append mode.
        record: Export record to serialize.
    """
    f.write(json.dumps(record, default=str) + "\n")
    f.flush()


def _export_batch(
    client: "ZammadClient",
    params: "TicketExportParams",
    batch: list[dict[str, Any]],
    f: TextIO,
    progress: _ExportProgress,
) -> None:
    """Export each ticket in a batch, recording per-ticket failures without stopping.

    Args:
        client: Zammad client used for per-ticket requests.
        params: Export parameters.
        batch: Ticket summaries from one page.
        f: Open output file.
        progress: Running totals, updated in place.
    """
    for ticket_summary in batch:
        ticket_id = ticket_summary.get("id")
        if not ticket_id:
            continue
        try:
            _write_export_line(f, _fetch_export_record(client, params, ticket_summary))
        except Exception as e:
            progress.record_error(ticket_id, e)
            continue
        progress.exported += 1
        if progress.limit_reached(params.max_tickets):
            return


_RATE_LIMIT_GUIDANCE = (
    "Error: Zammad rate limit reached during {context}{detail}. "
    "Wait before retrying, reduce request frequency or page size, or enable client-side "
    "throttling with ZAMMAD_RATE_LIMIT_ENABLED=true."
)
_SERVER_ERROR_GUIDANCE = (
    "Error: Zammad server error during {context}{detail}. "
    "The server is failing or temporarily unavailable; retry later or check the Zammad instance."
)

_API_ERROR_GUIDANCE: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("not found", "404"),
        "Error: Resource not found during {context}. Please verify the ID is correct and you have access.",
    ),
    (("forbidden", "403"), "Error: Permission denied for {context}. Your credentials lack access to this resource."),
    (("unauthorized", "401"), "Error: Authentication failed for {context}. Check ZAMMAD_HTTP_TOKEN is valid."),
    (("429", "too many requests", "rate limit"), _RATE_LIMIT_GUIDANCE),
    (
        ("timeout",),
        "Error: Request timeout during {context}. The server may be slow - try again or reduce the scope.",
    ),
    (
        ("connection", "network"),
        "Error: Network issue during {context}. Check ZAMMAD_URL is correct and the server is reachable.",
    ),
)


def _resilience_error_message(e: Exception, context: str) -> str | None:
    """Return guidance for retry-exhaustion or open-circuit errors, else None."""
    if isinstance(e, RetryExhaustedError):
        throttled = e.status_code == HTTPStatus.TOO_MANY_REQUESTS
        template = _RATE_LIMIT_GUIDANCE if throttled else _SERVER_ERROR_GUIDANCE
        return template.format(context=context, detail=f" ({e})")
    if isinstance(e, CircuitOpenError):
        return f"Error: Zammad is temporarily unavailable during {context} ({e}). Wait for the recovery timeout."
    return None


def _handle_api_error(e: Exception, context: str = "operation") -> str:
    """Format errors with actionable guidance for LLM agents.

    Args:
        e: The exception that occurred
        context: Description of what was being attempted

    Returns:
        Formatted error message with guidance
    """
    resilience_message = _resilience_error_message(e, context)
    if resilience_message is not None:
        return resilience_message

    error_msg = str(e).lower()

    # First matching pattern wins; order mirrors the original precedence.
    for patterns, template in _API_ERROR_GUIDANCE:
        if any(pattern in error_msg for pattern in patterns):
            return template.format(context=context, detail="")

    # Generic error with type information
    return f"Error during {context}: {type(e).__name__} - {e}"


# ============================================================================
# Knowledge Base helpers (read-only)
# ============================================================================


def _kb_answer_status(answer: dict[str, Any]) -> str:
    """Derive human-readable publication status from a KB answer dict."""
    if answer.get("archived_at"):
        return "archived"
    if answer.get("published_at"):
        return "published"
    if answer.get("internal_at"):
        return "internal"
    return "draft"


def _format_kb_markdown(kb: dict[str, Any]) -> str:
    """Format a KnowledgeBase dict as markdown."""
    lines = [f"# Knowledge Base (ID: {kb.get('id', 'N/A')})", ""]
    lines.append(f"**Active**: {kb.get('active', False)}")
    if kb.get("custom_address"):
        lines.append(f"**Address**: {kb['custom_address']}")
    lines.append(f"**Homepage Layout**: {kb.get('homepage_layout', 'N/A')}")
    lines.append(f"**Category Layout**: {kb.get('category_layout', 'N/A')}")
    cat_ids = kb.get("category_ids") or []
    ans_ids = kb.get("answer_ids") or []
    lines.append(f"**Root Categories**: {len(cat_ids)} (IDs: {cat_ids})")
    lines.append(f"**Answers**: {len(ans_ids)} total")
    lines.append(f"**Updated**: {kb.get('updated_at', 'N/A')}")
    return "\n".join(lines)


def _format_kb_category_markdown(category: dict[str, Any]) -> str:
    """Format a KnowledgeBaseCategory dict as markdown."""
    lines = [f"# KB Category (ID: {category.get('id', 'N/A')})", ""]
    lines.append(f"**Knowledge Base ID**: {category.get('knowledge_base_id', 'N/A')}")
    lines.append(f"**Parent ID**: {category.get('parent_id', 'None (root)')}")
    lines.append(f"**Icon**: {category.get('category_icon', 'N/A')}")
    lines.append(f"**Position**: {category.get('position', 0)}")
    child_ids = category.get("child_ids") or []
    answer_ids = category.get("answer_ids") or []
    translation_ids = category.get("translation_ids") or []
    lines.append(f"**Child Categories**: {len(child_ids)} (IDs: {child_ids})")
    lines.append(f"**Answers**: {len(answer_ids)} (IDs: {answer_ids})")
    lines.append(f"**Translation IDs**: {translation_ids}")
    lines.append(f"**Updated**: {category.get('updated_at', 'N/A')}")
    return "\n".join(lines)


def _format_kb_answer_optional_sections(answer: dict[str, Any], body: str) -> list[str]:
    """Build optional markdown sections (content, attachments, tags) for a KB answer."""
    lines: list[str] = []
    if body:
        lines += ["", "## Content", "", body.strip()]
    attachments = answer.get("attachments") or []
    if attachments:
        lines += ["", "## Attachments", ""]
        lines += [
            f"- **{att.get('filename', 'N/A')}** (ID: {att.get('id', 'N/A')}, size: {att.get('size', '?')} bytes)"
            for att in attachments
        ]
    tags = answer.get("tags") or []
    if tags:
        lines += ["", f"**Tags**: {', '.join(tags)}"]
    return lines


def _format_kb_answer_markdown(answer: dict[str, Any], title: str = "", body: str = "") -> str:
    """Format a KnowledgeBaseAnswer dict as markdown."""
    status = _kb_answer_status(answer)
    heading = title or f"KB Answer (ID: {answer.get('id', 'N/A')})"
    translation_ids = answer.get("translation_ids") or []
    lines = [
        f"# {heading}",
        "",
        f"**ID**: {answer.get('id', 'N/A')}",
        f"**Category ID**: {answer.get('category_id', 'N/A')}",
        f"**Status**: {status}",
        f"**Promoted**: {answer.get('promoted', False)}",
        f"**Position**: {answer.get('position', 0)}",
        f"**Translation IDs**: {translation_ids}",
    ]
    lines += _format_kb_answer_optional_sections(answer, body)
    lines += ["", f"**Updated**: {answer.get('updated_at', 'N/A')}"]
    return "\n".join(lines)


def _format_kb_answers_list_markdown(answers: list[dict[str, Any]], kb_id: int, category_id: int) -> str:
    """Format a list of KB answers as markdown."""
    lines = [f"# KB Answers in Category {category_id} (KB: {kb_id})", ""]
    lines.append(f"Found {len(answers)} answer(s)")
    lines.append("")
    for answer in answers:
        status = _kb_answer_status(answer)
        title = answer.get("_title") or "(no title)"
        lines.append(f"## {title} (ID: {answer.get('id', 'N/A')})")
        lines.append(f"- **Status**: {status}")
        lines.append(f"- **Promoted**: {answer.get('promoted', False)}")
        lines.append(f"- **Position**: {answer.get('position', 0)}")
        lines.append("")
    return "\n".join(lines)


def _format_kb_search_results_markdown(results: list[dict[str, Any]], query: str, kb_id: int) -> str:
    """Format KB answer search results as markdown."""
    if not results:
        return f"No KB answers found matching '{query}' in KB {kb_id}."
    lines = [f"# KB Answer Search: '{query}' (KB: {kb_id})", ""]
    lines.append(f"Found {len(results)} match(es)")
    lines.append("")
    for answer in results:
        title = answer.get("_title") or "(no title)"
        status = _kb_answer_status(answer)
        lines.append(f"## {title} (ID: {answer.get('id', 'N/A')})")
        lines.append(f"- **Category ID**: {answer.get('_category_id', answer.get('category_id', 'N/A'))}")
        lines.append(f"- **Status**: {status}")
        lines.append(f"- **Promoted**: {answer.get('promoted', False)}")
        lines.append("")
    return "\n".join(lines)


_BULK_TICKET_FIELDS = {"title", "state", "priority", "owner", "group", "time_unit"}


def _apply_bulk_ticket_actions(client: ZammadClient, ticket_id: int, params: BulkTicketUpdateParams) -> None:
    """Apply every requested bulk action to a single ticket.

    Args:
        client: Zammad client boundary.
        ticket_id: Internal ticket ID to modify.
        params: Validated bulk request describing the actions.

    Raises:
        Exception: Any client error from the first failing action.
    """
    fields = params.model_dump(include=_BULK_TICKET_FIELDS, exclude_none=True)
    if fields:
        client.update_ticket(ticket_id=ticket_id, **fields)
    for tag in params.add_tags or []:
        client.add_ticket_tag(ticket_id, tag)
    for tag in params.remove_tags or []:
        client.remove_ticket_tag(ticket_id, tag)
    if params.note is not None:
        client.add_article(ticket_id=ticket_id, body=params.note, article_type="note", internal=True)


def _run_bulk_ticket_update(client: ZammadClient, params: BulkTicketUpdateParams) -> BulkUpdateResult:
    """Process tickets sequentially, collecting per-ticket outcomes.

    Args:
        client: Zammad client boundary.
        params: Validated bulk request.

    Returns:
        BulkUpdateResult: Successful IDs, failures with reasons, and totals.
    """
    successful: list[int] = []
    failed: list[BulkUpdateFailure] = []
    last_index = len(params.ticket_ids) - 1
    for index, ticket_id in enumerate(params.ticket_ids):
        try:
            _apply_bulk_ticket_actions(client, ticket_id, params)
            successful.append(ticket_id)
        except Exception as e:
            error = _handle_api_error(e, f"bulk update of ticket {ticket_id}")
            failed.append(BulkUpdateFailure(ticket_id=ticket_id, error=error))
        if params.delay_seconds and index < last_index:
            time.sleep(params.delay_seconds)
    return BulkUpdateResult(
        successful_ticket_ids=successful,
        failed=failed,
        total_processed=len(params.ticket_ids),
        total_successful=len(successful),
    )


def _queue_count_label(fetched: int) -> str:
    """Label the queue ticket count without claiming a total for a full page.

    Args:
        fetched: Number of tickets on the fetched page, before the per-state display cap.

    Returns:
        "Tickets fetched: N", with " (first N)" appended when the page is full.
    """
    suffix = f" (first {QUEUE_PAGE_SIZE})" if fetched >= QUEUE_PAGE_SIZE else ""
    return f"Tickets fetched: {fetched}{suffix}"


def _format_queue_ticket(ticket: dict[str, Any]) -> list[str]:
    """Format one queue ticket as three indented lines.

    Args:
        ticket: Raw ticket dictionary from search.

    Returns:
        Lines with number/ID/title, priority/customer, and creation time.
    """
    priority = ticket.get("priority", {})
    priority_name = priority.get("name", "Unknown") if isinstance(priority, dict) else str(priority)
    customer = ticket.get("customer", {})
    customer_email = customer.get("email", "Unknown") if isinstance(customer, dict) else str(customer)
    title = str(ticket.get("title", "No title"))
    short = title[:50]
    suffix = "..." if len(title) > len(short) else ""
    return [
        f"  #{ticket.get('number', 'N/A')} (ID: {ticket.get('id', 'N/A')}) - {short}{suffix}",
        f"    Priority: {priority_name}, Customer: {customer_email}",
        f"    Created: {ticket.get('created_at', 'Unknown')}",
    ]


def _format_queue_state(state: str, state_tickets: list[dict[str, Any]]) -> list[str]:
    """Format one state section of the queue, capped at MAX_TICKETS_PER_STATE_IN_QUEUE.

    Args:
        state: State name used as the section heading.
        state_tickets: Tickets in that state.

    Returns:
        Heading, ticket lines, an overflow note when capped, and a blank line.
    """
    lines = [f"{state.title()} ({len(state_tickets)} tickets):"]
    for ticket in state_tickets[:MAX_TICKETS_PER_STATE_IN_QUEUE]:
        lines.extend(_format_queue_ticket(ticket))
    overflow = len(state_tickets) - MAX_TICKETS_PER_STATE_IN_QUEUE
    if overflow > 0:
        lines.append(f"    ... and {overflow} more tickets")
    lines.append("")
    return lines


class ZammadMCPServer:
    """Zammad MCP Server with proper client lifecycle management."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        *,
        audit_logger: AuditLogger | None = None,
        event_store: EventStore | None = None,
    ) -> None:
        """Initialize the server.

        Args:
            host: Deprecated. Pass host to mcp.run() instead.
            port: Deprecated. Pass port to mcp.run() instead.
            audit_logger: Audit sink for tool-call and lifecycle events. Defaults to
                one built from the ZAMMAD_AUDIT_LOG_* environment variables.
            event_store: Optional. Retention for accepted webhook events; defaults to a bounded in-memory store.

        """
        if host is not None or port is not None:
            logger.warning("ZammadMCPServer(host=..., port=...) is deprecated; pass host/port to mcp.run(...) instead.")
        self.client: ZammadClient | None = None
        self._connected_user_id: int | str | None = None
        # Load .env early so audit settings and AuthConfig.from_env() see .env-sourced variables.
        self._bootstrap_env()
        self.audit = audit_logger or AuditLogger(AuditConfig.from_env(os.environ))
        self.event_store = event_store if event_store is not None else EventStore()

        # Configure authentication from environment. OAuth needs the HTTP transport;
        # stdio has no inbound request layer, so it keeps the static Zammad credentials.
        self.auth_config = AuthConfig.from_env()
        transport = os.getenv("MCP_TRANSPORT", TransportType.STDIO.value).lower()
        if self.auth_config.enabled and transport != TransportType.HTTP.value:
            logger.warning(
                "MCP_AUTH_* variables are set but MCP_TRANSPORT is %r. OAuth requires MCP_TRANSPORT=http; "
                "ignoring the OAuth settings and using the static Zammad credentials.",
                transport,
            )
            self.auth_config = AuthConfig()
        auth_provider = self.auth_config.create_auth_provider()

        # Create FastMCP with lifespan and optional auth configured
        self.mcp = FastMCP("zammad_mcp", lifespan=self._create_lifespan(), auth=auth_provider)
        if self.audit.enabled:
            self.mcp.add_middleware(AuditMiddleware(self.audit))
        self._setup_tools()
        self._setup_resources()
        self._setup_prompts()
        self._setup_webhooks()

    def _bootstrap_env(self) -> None:
        """Load local environment files before client initialization."""
        cwd_env = Path.cwd() / ".env"
        if cwd_env.exists():
            load_dotenv(cwd_env)
            logger.info("Loaded environment from %s", cwd_env)

        envrc_path = Path.cwd() / ".envrc"
        if envrc_path.exists() and not os.environ.get("ZAMMAD_URL"):
            logger.warning(
                "Found .envrc but environment variables not loaded. Consider using direnv or creating a .env file"
            )

        load_dotenv()

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

    def _create_client(self, *, verify_connection: bool) -> ZammadClient:
        """Create a Zammad client after loading environment configuration."""
        self._bootstrap_env()
        client = ZammadClient(audit_logger=self.audit)
        logger.info("Zammad client initialized successfully")

        if verify_connection:
            current_user = client.get_current_user()
            self._connected_user_id = current_user.get("id")
            logger.info("Connected as user ID: %s", self._connected_user_id or "unknown")

        return client

    def get_client(self) -> ZammadClient:
        """Get the Zammad client, ensuring it's initialized.

        When auth is enabled, creates a per-request client using the
        authenticated user's upstream access token.  When auth is disabled,
        returns the shared static client with lazy initialization.
        """
        if self.auth_config.enabled:
            return self._get_authenticated_client()
        if not self.client:
            logger.debug("Zammad client not initialized, performing lazy initialization")
            self.client = self._create_client(verify_connection=False)
        return self.client

    def _get_authenticated_client(self) -> ZammadClient:
        """Create a ZammadClient using the current request's upstream token."""
        access_token = get_access_token()
        if access_token is None:
            raise RuntimeError(
                "No access token in request context. "
                "Ensure the MCP client authenticates via the configured auth provider."
            )

        return ZammadClient(oauth2_token=access_token.token, audit_logger=self.audit)

    async def initialize(self) -> None:
        """Initialize the Zammad client on server startup."""
        if self.auth_config.enabled:
            logger.info("OAuth auth enabled (%s) — clients created per-request", self.auth_config.zammad_base_url)
            return

        try:
            self.client = self._create_client(verify_connection=True)
        except Exception as exc:
            logger.exception("Failed to initialize Zammad client")
            self.audit.log_event("authentication", "zammad_connect", success=False, details=error_details(exc))
            raise
        details = {"user_id": self._connected_user_id}
        self.audit.log_event("authentication", "zammad_connect", success=True, details=details)

    def _setup_tools(self) -> None:
        """Register all tools with the MCP server."""
        self._setup_ticket_tools()
        self._setup_export_tools()
        self._setup_user_org_tools()
        self._setup_system_tools()
        self._setup_kb_tools()
        self._setup_event_tools()

    def _setup_webhooks(self) -> None:
        """Expose the Zammad webhook ingress route (HTTP transport only)."""
        handler = WebhookHandler(
            secret_provider=lambda: os.getenv("ZAMMAD_WEBHOOK_SECRET"),
            clock=lambda: datetime.now(timezone.utc),
            sink=self.event_store,
        )

        @self.mcp.custom_route("/webhooks/zammad", methods=["POST"])
        async def zammad_webhook(request: Request) -> JSONResponse:
            result = handler.handle_delivery(await request.body(), request.headers)
            return JSONResponse(result.body, status_code=result.status_code)

    def _setup_event_tools(self) -> None:
        """Register tools that read retained webhook events."""

        @self.mcp.tool(annotations=_read_only_annotations("List Webhook Events"))
        @flat_params(ListEventsParams)
        def zammad_list_events(params: ListEventsParams) -> ListEventsResult:
            """List Zammad ticket events received via webhook, oldest first.

            Events arrive only when the server runs with HTTP transport and a Zammad
            webhook + trigger POST to `/webhooks/zammad` with a valid HMAC-SHA1 signature.
            Retention is process-local and bounded (`capacity`); events are lost on restart.

            Parameters:
                since (datetime | None): Only events received strictly after this timestamp
                limit (int): Maximum events per page, 1-100 (default: 50); the oldest
                    matching events are returned first

            Returns:
                ListEventsResult: `events` (event_type, ticket_id, ticket_number, article_id,
                trigger, source_timestamp, received_at), `count`, `capacity`, `retained_total`,
                and `next_since` (pass back as `since` on the next call; null when no events).
                Keep calling with `next_since` until `events` is empty to drain a backlog
                larger than `limit` without skipping anything.

            Examples:
                - Use when: "Any new ticket activity?" -> poll with since=<last next_since>
                - Use when: "Which tickets changed recently?" -> then zammad_get_ticket per ticket_id
                - Don't use when: You need ticket content (this returns identifiers only)

            Error Handling:
                - Returns a validation error if limit is outside 1-100 or since is not ISO 8601
                - With OAuth enabled, events for tickets the caller cannot read are left out,
                  so a page can hold fewer than `limit` events; keep following `next_since`
            """
            if self.auth_config.enabled:
                events, next_since = self._list_permitted_events(params.since, params.limit)
            else:
                events = self.event_store.list(since=params.since, limit=params.limit)
                next_since = events[-1].received_at if events else None
            return ListEventsResult(
                events=events,
                count=len(events),
                capacity=self.event_store.capacity,
                retained_total=len(self.event_store),
                next_since=next_since,
            )

    def _list_permitted_events(self, since: datetime | None, limit: int) -> tuple[list[WebhookEvent], datetime | None]:
        """Return the next page of events whose ticket the request's user may read.

        The event store is shared by every user of the process, while OAuth users
        hold different Zammad permissions. Pages whose events are all hidden are
        skipped, so an empty result means the store holds nothing further for this
        user and callers that stop on an empty page miss nothing. The cursor covers
        every scanned event, hidden ones included. Each distinct ticket is checked once.
        """
        client = self.get_client()
        access: dict[int, bool] = {}
        cursor, next_since = since, None
        while page := self.event_store.list(since=cursor, limit=limit):
            cursor = next_since = page[-1].received_at
            permitted = []
            for event in page:
                if event.ticket_id not in access:
                    access[event.ticket_id] = client.can_access_ticket(event.ticket_id)
                if access[event.ticket_id]:
                    permitted.append(event)
            if permitted:
                return permitted, next_since
        return [], next_since

    def _setup_ticket_tools(self) -> None:  # noqa: PLR0915
        """Register ticket-related tools."""

        @self.mcp.tool(annotations=_read_only_annotations("Search Tickets"))
        @flat_params(TicketSearchParams)
        def zammad_search_tickets(params: TicketSearchParams) -> str:
            """Search for tickets with filters and pagination.

            Combine a free-text query with state, priority, group, owner (login), and customer
            (email) filters. Search by ticket number here to get the internal ID that other tools
            need. With a known ID use zammad_get_ticket.

            Args:
                params (TicketSearchParams): Validated search parameters containing:
                    - query (str | None): Search string (matches title, body, tags)
                    - state (str | None): Filter by state name (e.g., "open", "closed")
                    - priority (str | None): Filter by priority name (e.g., "high")
                    - group (str | None): Filter by group name
                    - owner (str | None): Filter by owner login (sent as owner.login:<value>)
                    - customer (str | None): Filter by customer email (sent as customer.email:<value>)
                    - created_after (date | None): Only tickets created on/after YYYY-MM-DD
                    - created_before (date | None): Only tickets created on/before YYYY-MM-DD
                    - page (int): Page number (default: 1)
                    - per_page (int): Results per page, 1-100 (default: 25)
                    - response_format (ResponseFormat): Output format - markdown or json (default: markdown)

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

                JSON format (abbreviated example; items are full Ticket model dumps):
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
                    "count": 25,
                    "page": 1,
                    "per_page": 25,
                    "offset": 0,
                    "has_more": true,
                    "next_page": 2,
                    "next_offset": 25,
                    "_meta": {}
                }
                ```

                total is always null (Zammad search reports no total); has_more is the
                heuristic count == per_page.

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
                "created_after": params.created_after,
                "created_before": params.created_before,
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
        @flat_params(GetTicketParams)
        def zammad_get_ticket(params: GetTicketParams) -> str:
            """Get detailed information about a specific ticket by ID.

            Use the internal ticket ID, not the ticket number shown in Zammad; if you only have
            the number, find the ID with zammad_search_tickets. An unknown ID raises an error that
            explains the difference.

            Parameters:
                ticket_id (int): Internal database ID (NOT display number) (required)
                include_articles (bool): Include ticket articles/comments (default: True)
                article_limit (int): Maximum articles to return, -1 for all (default: 10)
                article_offset (int): Number of articles to skip for pagination (default: 0)
                response_format (ResponseFormat): Output format - markdown or json (default: markdown)

            Returns:
                str: Formatted response with the following schema:

                Markdown format (default):
                ```
                # Ticket #65003 - Server not responding

                **ID**: 123
                **State**: open
                **Priority**: high
                **Group**: Support
                **Owner**: agent@example.com
                **Customer**: user@example.com
                **Created**: 2024-01-15T10:30:00Z
                **Updated**: 2024-01-15T14:20:00Z

                ## Articles
                ...
                ```

                JSON format (abbreviated example; the full Ticket model is dumped):
                ```json
                {
                    "id": 123,
                    "number": "65003",
                    "title": "Server not responding",
                    "state": {"id": 1, "name": "open"},
                    "priority": {"id": 2, "name": "high"},
                    "customer": {"id": 5, "email": "user@example.com"},
                    "group": {"id": 3, "name": "Support"},
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T14:20:00Z",
                    "articles": [{"id": 456, "body": "...", "created_at": "2024-01-15T10:30:00Z"}]
                }
                ```

            Examples:
                - Use when: "Get details for ticket 123" -> ticket_id=123
                - Use when: "Show ticket with articles" -> ticket_id=123, include_articles=True
                - Don't use when: Searching for tickets by criteria (use zammad_search_tickets)
                - Don't use when: You only have ticket number (search first to get ID)

            Error Handling:
                - Raises TicketIdGuidanceError (via _handle_ticket_not_found_error) when Zammad
                  reports the ticket as not found; the message explains ID vs number
                - Any other exception (Zammad HTTP error text for 401/403, network errors)
                  propagates unchanged; FastMCP returns a tool error with the exception text

            Note:
                ticket_id must be the internal database ID, NOT the display number.
                Use the 'id' field from search results, not the 'number' field.
                Example: Ticket #65003 may have id=123. Use id=123 for API calls.
                Large tickets may exceed token limits; use article_limit to control size.
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
        @flat_params(TicketCreate)
        def zammad_create_ticket(params: TicketCreate) -> Ticket:
            """Create a new ticket in Zammad with initial article.

            The customer must already exist in Zammad; create one with zammad_create_user if
            needed. Group, state, and priority take names from zammad_list_groups,
            zammad_list_ticket_states, and zammad_list_ticket_priorities. To comment on an
            existing ticket use zammad_add_article.

            Args:
                params (TicketCreate): Validated ticket creation parameters containing:
                    - title (str): Ticket title/subject (required)
                    - group (str): Group name or ID (required; forwarded to Zammad as-is)
                    - customer (str): Customer email or ID (required, must exist in Zammad;
                      forwarded to Zammad as-is)
                    - article_body (str): Initial article/comment body (required)
                    - state (str): State name (default: "new")
                    - priority (str): Priority name (default: "2 normal")
                    - article_type (str): Article type - "note", "email", "phone" (default: "note")
                    - article_internal (bool): Whether article is internal-only (default: False)

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
                - Use when: "Create ticket for server outage" -> title, group, customer, article_body
                - Use when: "New high priority ticket" -> add priority="3 high"
                - Don't use when: Ticket already exists (use zammad_update_ticket)
                - Don't use when: Only adding comment (use zammad_add_article)

            Error Handling:
                - Missing or oversized fields fail Pydantic validation before any API call;
                  FastMCP returns the validation error as a tool error
                - Raises ValueError with customer guidance (check with zammad_search_users,
                  create with zammad_create_user) when Zammad's error mentions the customer
                  as not found / couldn't find / lookup
                - Any other exception (Zammad HTTP error text for 401/403/422, e.g. unknown
                  group or state) propagates; FastMCP returns a tool error with that text

            Note:
                The customer must exist in Zammad before creating a ticket.
                Use zammad_create_user to create new customers first.
            """
            client = self.get_client()
            try:
                ticket_data = client.create_ticket(**params.model_dump(exclude_none=True, mode="json"))
                return Ticket(**ticket_data)
            except Exception as e:
                error_msg = str(e).lower()
                if "customer" in error_msg and (
                    "not found" in error_msg or "couldn't find" in error_msg or "lookup" in error_msg
                ):
                    raise ValueError(
                        f"Customer '{params.customer}' not found in Zammad. "
                        f"Note: Customers must exist before creating tickets. "
                        f"Use zammad_search_users to check, or zammad_create_user to create. "
                        f"Example: zammad_create_user(email='{params.customer}', firstname='...', lastname='...')"
                    ) from e
                raise

        @self.mcp.tool(annotations=_write_annotations("Update Ticket"))
        @flat_params(TicketUpdateParams)
        def zammad_update_ticket(params: TicketUpdateParams) -> Ticket:
            """Update an existing ticket's fields.

            Use the internal ticket ID. State, priority, and group take names; the customer must
            already exist. To comment use zammad_add_article; to tag use zammad_add_ticket_tag.

            Args:
                params (TicketUpdateParams): Validated update parameters containing:
                    - ticket_id (int): Internal database ID (required, NOT display number)
                    - title (str | None): New title
                    - state (str | None): New state name
                    - priority (str | None): New priority name
                    - group (str | None): New group name
                    - owner (str | None): New owner email/login
                    - customer (str | None): New customer email/login
                    - pending_time (datetime | None): Pending-until timestamp (ISO 8601),
                      required when state is "pending reminder" or "pending close"
                    - time_unit (float | None): Time spent for time accounting
                    - custom_fields (dict[str, Any] | None): Custom object attributes defined in
                      Zammad Admin, keyed by attribute name (e.g. {"region": "north"})

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
                - Use when: "Set ticket 123 to pending until 2026-07-01" ->
                  ticket_id=123, state="pending reminder", pending_time="2026-07-01T08:00:00Z"
                - Use when: "Reassign ticket to Alice" -> ticket_id=123, owner="alice@company.com"
                - Use when: "Set region to north on ticket 123" -> ticket_id=123, custom_fields={"region": "north"}
                - Don't use when: Adding comments (use zammad_add_article)
                - Don't use when: Adding tags (use zammad_add_ticket_tag)

            Error Handling:
                - Raises TicketIdGuidanceError (via _handle_ticket_not_found_error) when Zammad
                  reports the ticket as not found; the message explains ID vs number
                - Invalid field values fail Pydantic validation before any API call
                - Any other exception (Zammad HTTP error text for 401/403/422, e.g. unknown
                  group/owner/customer) propagates; FastMCP returns a tool error with that text

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
        @flat_params(ArticleCreate)
        def zammad_add_article(params: ArticleCreate) -> Article:
            """Add an article (comment/note/email) to an existing ticket with optional attachments.

            Use the internal ticket_id, not the ticket number. Set internal=true for a note that
            only agents see. text/plain bodies are HTML-escaped before sending. To open a ticket
            use zammad_create_ticket; to change ticket fields use zammad_update_ticket.

            Args:
                params (ArticleCreate): Validated article creation parameters containing:
                    - ticket_id (int): Internal database ID (required, NOT display number)
                    - body (str): Article content/message (required)
                    - article_type (ArticleType): Article type - note, email, or phone (default: note)
                    - internal (bool): Internal note vs customer-visible (default: False)
                    - sender (ArticleSender): Agent, Customer, or System (default: Agent)
                    - subject (str | None): Article subject (for emails)
                    - content_type (str | None): text/plain or text/html (default: text/plain).
                      text/plain bodies are HTML-escaped (<, >, &) by ArticleCreate.sanitize_body;
                      text/html bodies have script tags and javascript: URLs neutralized
                    - to (str | None): Email recipient (for email type)
                    - cc (str | None): Email CC recipients
                    - time_unit (float | None): Time spent for time accounting (> 0)
                    - attachments (list[AttachmentUpload] | None): Optional attachments (max 10)

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
                - Use when: "Add note to ticket 123" -> ticket_id=123, body="text", article_type="note"
                - Use when: "Reply to customer" -> ticket_id=123, body="reply", article_type="email"
                - Use when: "Internal comment" -> ticket_id=123, body="note", article_type="note", internal=True
                - Use when: "Upload files with article" -> ticket_id=123, body="See attached", attachments=[...]
                - Don't use when: Creating new ticket (use zammad_create_ticket with article)
                - Don't use when: Updating ticket fields (use zammad_update_ticket)

            Error Handling:
                - A missing body or an unknown article_type fails Pydantic validation before
                  any API call
                - Zammad errors (HTTP error text for 401/403/404, e.g. unknown ticket_id)
                  propagate unchanged; FastMCP returns a tool error with that text
                - Sanitizes HTML content if content_type is text/html
                - Validates base64 encoding before upload
                - Sanitizes filenames to prevent path traversal
                - Limits to 10 attachments per article

            Note:
                ticket_id must be the internal database ID, NOT the display number.
                Use the 'id' field from search results, not the 'number' field.
                Example: Ticket #65003 may have id=123. Use id=123 for API calls.
                Internal articles are only visible to agents, not customers.
            """
            client = self.get_client()

            # Convert Pydantic attachments to dict format for client
            attachments_data = None
            if params.attachments:
                attachments_data = [
                    {
                        "filename": att.filename,
                        "data": att.data,
                        "mime-type": att.mime_type,
                    }
                    for att in params.attachments
                ]

            # Extract ticket_id and article_type separately to avoid duplicate kwargs
            # Use mode="json" to convert enums to strings, by_alias=True for API compatibility
            article_params = params.model_dump(
                mode="json", by_alias=True, exclude={"ticket_id", "article_type", "attachments"}
            )
            article_data = client.add_article(
                ticket_id=params.ticket_id,
                article_type=params.article_type.value,
                attachments=attachments_data,
                **article_params,
            )

            return Article(**article_data)

        @self.mcp.tool(annotations=_read_only_annotations("Get Article Attachments"))
        @flat_params(GetArticleAttachmentsParams)
        def zammad_get_article_attachments(params: GetArticleAttachmentsParams) -> list[Attachment]:
            """Get list of attachments for a specific article in a ticket.

            Returns metadata only: id, filename, size, content_type, and created_at. Only
            article_id is looked up; ticket_id is not checked. To get file content use
            zammad_download_attachment.

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
                        "size": 245678,
                        "content_type": "image/png",
                        "created_at": "2024-01-15T10:30:00Z"
                    }
                ]
                ```

                size, content_type, and created_at are null when Zammad omits them.

            Examples:
                - Use when: "List attachments for article 456 in ticket 123" -> ticket_id=123, article_id=456
                - Use when: "Check if article has attachments" -> ticket_id=123, article_id=456
                - Don't use when: Downloading attachment content (use zammad_download_attachment)
                - Don't use when: Article ID unknown (use zammad_get_ticket with include_articles first)

            Error Handling:
                - Returns empty list if article has no attachments
                - ticket_id is validated (> 0) but never sent to Zammad: the client looks up
                  article_id alone, so a wrong ticket_id does not produce an error
                - Zammad errors (HTTP error text for 401/403/404, e.g. unknown article_id)
                  propagate unchanged; FastMCP returns a tool error with that text

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
        @flat_params(DownloadAttachmentParams)
        def zammad_download_attachment(params: DownloadAttachmentParams) -> str:
            """Download attachment file content from a ticket article.

            Returns the file content as base64. max_bytes defaults to 10,000,000; a larger file
            raises an error unless you raise the limit or pass null for no limit. Get the IDs from
            zammad_get_article_attachments.

            Args:
                params (DownloadAttachmentParams): Validated parameters containing:
                    - ticket_id (int): Internal database ID (required, NOT display number)
                    - article_id (int): Article ID containing attachment (required)
                    - attachment_id (int): Attachment ID to download (required)
                    - max_bytes (int | None): Maximum file size limit (default: 10000000); null disables the limit

            Returns:
                str: Base64-encoded binary content of the attachment file.
                     Decode using base64.b64decode() to get original bytes.

            Examples:
                - Use when: "Download attachment 789 from article 456" -> ticket_id=123, article_id=456, attachment_id=789
                - Use when: "Get file with size limit" -> ticket_id=123, article_id=456, attachment_id=789, max_bytes=1000000
                - Don't use when: Only need attachment metadata (use zammad_get_article_attachments)
                - Don't use when: Attachment IDs unknown (list attachments first)

            Error Handling:
                - Raises AttachmentDownloadError if download fails; request errors (including
                  Zammad HTTP errors for 401/403/404 on unknown IDs) and ValueErrors are wrapped
                  into it with the original error text
                - Raises AttachmentDownloadError if file exceeds max_bytes limit
                - FastMCP returns the AttachmentDownloadError as a tool error with its text

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

        @self.mcp.tool(annotations=_destructive_write_annotations("Merge Tickets"))
        @flat_params(TicketMergeParams)
        def zammad_merge_tickets(params: TicketMergeParams) -> TicketMergeResult:
            """Merge a source ticket into a target ticket.

            All articles from the source ticket are moved to the target and the
            source is closed with state "merged". This cannot be undone.

            Parameters:
                source_ticket_id (int): Internal ID of the ticket to merge away (required)
                target_ticket_number (str, optional): Display number of the surviving ticket
                target_ticket_id (int, optional): Internal ID of the surviving ticket
                Exactly one of target_ticket_number or target_ticket_id is required.

            Returns:
                TicketMergeResult with the Zammad result and the surviving target ticket

            Examples:
                - Use when: Collapsing duplicate auto-generated tickets (cron failures,
                  monitoring noise) into a single incident ticket
                - Don't use when: Unsure which ticket should survive (search first)

            Note:
                Requires agent permissions on both tickets. Irreversible.
            """
            client = self.get_client()
            payload = client.merge_tickets(
                source_ticket_id=params.source_ticket_id,
                target_ticket_number=params.target_ticket_number,
                target_ticket_id=params.target_ticket_id,
            )
            return TicketMergeResult(result=payload["result"], target_ticket=Ticket(**payload["target_ticket"]))

        @self.mcp.tool(annotations=_idempotent_write_annotations("Add Ticket Tag"))
        @flat_params(TagOperationParams)
        def zammad_add_ticket_tag(params: TagOperationParams) -> TagOperationResult:
            """Add a tag to a ticket (idempotent operation).

            Adding a tag the ticket already has changes nothing. Use the internal ticket_id. To
            remove a tag use zammad_remove_ticket_tag.

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
                - Zammad errors (HTTP error text for 401/403/404, e.g. unknown ticket_id)
                  propagate unchanged; FastMCP returns a tool error with that text

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
        @flat_params(TagOperationParams)
        def zammad_remove_ticket_tag(params: TagOperationParams) -> TagOperationResult:
            """Remove a tag from a ticket (idempotent operation).

            Removing a tag the ticket does not have changes nothing. Use the internal ticket_id.
            To add a tag use zammad_add_ticket_tag.

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
                - Zammad errors (HTTP error text for 401/403/404, e.g. unknown ticket_id)
                  propagate unchanged; FastMCP returns a tool error with that text

            Note:
                ticket_id must be the internal database ID, NOT the display number.
                Use the 'id' field from search results, not the 'number' field.
                Example: Ticket #65003 may have id=123. Use id=123 for API calls.
                This operation is idempotent - removing non-existent tag succeeds.
            """
            client = self.get_client()
            result = client.remove_ticket_tag(params.ticket_id, params.tag)
            return TagOperationResult(**result)

    def _setup_export_tools(self) -> None:
        """Register export-related tools."""

        @self.mcp.tool(annotations=_write_annotations("Export Tickets to JSONL"))
        @flat_params(TicketExportParams)
        def zammad_export_tickets(params: TicketExportParams) -> str:
            """Export tickets with conversation articles to a JSONL file for AI training.

            The tool fails when ZAMMAD_EXPORT_DIR is not set, and output_path must resolve inside
            that directory.

            Fetches tickets in batches, retrieves all articles for each ticket,
            strips HTML to plain text, and writes one JSON line per ticket.

            By default (no filters), uses the list endpoint which has no result cap.
            When filters are specified, uses the search endpoint (capped at 10,000 results).

            Args:
                params (TicketExportParams): Export parameters containing:
                    - output_path (str): Path to output JSONL file (must end in .jsonl).
                      Relative to ZAMMAD_EXPORT_DIR; absolute paths must resolve inside it.
                    - query (str | None): Free text search filter
                    - group (str | None): Filter by group name
                    - state (str | None): Filter by state name
                    - created_after (date | None): Filter tickets created on/after date (YYYY-MM-DD)
                    - created_before (date | None): Filter tickets created on/before date (YYYY-MM-DD)
                    - delay_seconds (float): Delay between API calls, 0-10 (default: 0.5)
                    - per_page (int): Batch size per page, 1-100 (default: 50)
                    - include_internal_articles (bool): Include internal notes (default: False)
                    - resume_from_page (int): Page to resume from (default: 1)
                    - max_tickets (int | None): Maximum tickets to export (default: None)
                    - include_tags (bool): Fetch per-ticket tags via an extra API call (default: False)

            Returns:
                str: Markdown summary with file path, counts, elapsed time, and errors

            Raises:
                ValueError: If ZAMMAD_EXPORT_DIR is unset, does not exist or is not a
                    directory, or the resolved output_path falls outside it (symlinks are
                    resolved first). FastMCP returns the message as a tool error.

            JSONL record format (one per line):
                ```json
                {
                    "ticket_id": 123,
                    "ticket_number": "65003",
                    "title": "Subject line",
                    "group": "Support",
                    "state": "closed",
                    "priority": "2 normal",
                    "tags": ["network"],
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-02-01T14:22:00Z",
                    "conversation": [
                        {
                            "sender": "Customer",
                            "type": "email",
                            "from": "user@example.com",
                            "subject": "Subject line",
                            "body": "Plain text body...",
                            "internal": false,
                            "created_at": "2024-01-15T10:30:00Z"
                        }
                    ]
                }
                ```

            Note:
                - The file is opened in append mode to support resume from interruption.
                - Each line is flushed immediately so progress survives crashes.
                - Errors on individual tickets are logged but do not stop the export.
                - The search endpoint is capped at 10,000 results by Zammad.
            """
            client = self.get_client()
            start_time = time.monotonic()

            use_search = any([params.query, params.group, params.state, params.created_after, params.created_before])

            export_path = _resolve_export_path(params.output_path)

            progress = _ExportProgress()

            with open(export_path, "a") as f:
                for batch in _iter_export_batches(client, params, use_search):
                    _export_batch(client, params, batch, f, progress)
                    if progress.limit_reached(params.max_tickets):
                        break

            elapsed = time.monotonic() - start_time
            return _format_export_summary(
                params, progress.exported, progress.error_count, progress.errors, elapsed, use_search, export_path
            )

        @self.mcp.tool(annotations=_destructive_write_annotations("Bulk Update Tickets"))
        @flat_params(BulkTicketUpdateParams)
        def zammad_bulk_update_tickets(params: BulkTicketUpdateParams) -> BulkUpdateResult:
            """Apply the same changes to up to 100 tickets in one call (update, assign, tag, close).

            Supply at least one field, tag, or note. The call is not atomic: successful_ticket_ids
            lists tickets where every requested action succeeded, and failed lists the others with
            their errors. For one ticket use zammad_update_ticket.

            Parameters:
                ticket_ids (list[int]): 1-100 unique internal database IDs (NOT display numbers) (required)
                title, state, priority, owner, group, time_unit: Same semantics as zammad_update_ticket
                add_tags (list[str] | None): Tags to add to every ticket
                remove_tags (list[str] | None): Tags to remove from every ticket
                note (str | None): Internal note added to every ticket
                delay_seconds (float): Pause between tickets (default 0)
                At least one field, tag, or note must be supplied.

            Returns:
                BulkUpdateResult: Per-ticket outcome summary with schema:

                ```json
                {
                    "successful_ticket_ids": [1, 3],
                    "failed": [{"ticket_id": 2, "error": "Error: Resource not found ..."}],
                    "total_processed": 3,
                    "total_successful": 2
                }
                ```

            Examples:
                - Use when: "Close tickets 1, 2, 3" -> ticket_ids=[1, 2, 3], state="closed"
                - Use when: "Assign these to Alice" -> ticket_ids=[...], owner="alice@company.com"
                - Use when: "Tag all as vip" -> ticket_ids=[...], add_tags=["vip"]
                - Use when: "Close with a note" -> ticket_ids=[...], state="closed", note="Resolved"
                - Don't use when: Changing a single ticket (use zammad_update_ticket)
                - Don't use when: More than 100 tickets (split into multiple calls)

            Error Handling:
                - Tickets are processed one at a time; a failure never stops the batch
                - Each failure is reported in `failed` with an actionable message
                - A ticket appears in successful_ticket_ids only if every requested action succeeded
                - Zammad has no bulk endpoint: earlier tickets stay changed if a later one fails

            Note:
                This is a destructive, non-atomic operation. Review ticket_ids carefully
                (use zammad_search_tickets first) before applying mass state or owner changes.
            """
            return _run_bulk_ticket_update(self.get_client(), params)

    def _setup_user_org_tools(self) -> None:
        """Register user and organization tools."""

        @self.mcp.tool(annotations=_read_only_annotations("Get User Details"))
        @flat_params(GetUserParams)
        def zammad_get_user(params: GetUserParams) -> str:
            """Get detailed information about a specific user by ID.

            Use the internal user ID; to find a user by email or name use zammad_search_users. For
            the authenticated account use zammad_get_current_user.

            Parameters:
                user_id (int): User's internal database ID (required)
                response_format (ResponseFormat): Output format - markdown or json (default: markdown)

            Returns:
                str: Formatted user information.
                     - Markdown format: name, ID, login, email, active/vip/verified flags, then
                       optional Organization, Contact, Address, Out of Office, and Notes sections,
                       and a Metadata section (created, updated, last login)
                     - JSON format: the User model (id, organization_id, login, email, firstname,
                       lastname, image, web, phone, fax, mobile, department, street, zip, city,
                       country, address, vip, verified, active, note, last_login, out_of_office*,
                       created_by_id, updated_by_id, created_at, updated_at, organization,
                       created_by, updated_by). Roles, preferences, and custom attributes are not
                       part of the model and are dropped. The client call does not request
                       expanded data, so organization/created_by/updated_by are usually null
                       unless Zammad returns them.

                Abbreviated example JSON response:
                ```json
                {
                    "id": 5,
                    "login": "user@example.com",
                    "firstname": "Jane",
                    "lastname": "Doe",
                    "email": "user@example.com",
                    "organization": {"id": 2, "name": "ACME Corp"},
                    "active": true,
                    "vip": false,
                    "created_at": "2023-01-10T08:00:00Z"
                }
                ```

            Examples:
                - Use when: "Get details for user 5" -> user_id=5
                - Use when: "Show user information" -> user_id=5
                - Don't use when: Searching by email/name (use zammad_search_users)
                - Don't use when: Getting current authenticated user (use zammad_get_current_user)

            Error Handling:
                - Zammad errors (HTTP error text for 401/403/404, e.g. unknown user_id)
                  propagate unchanged; FastMCP returns a tool error with that text

            Note:
                Returns the standard User model fields only; roles, preferences, and custom
                attributes are not included.
                Use zammad_search_users if you need to find users by email or name.
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
        @flat_params(SearchUsersParams)
        def zammad_search_users(params: SearchUsersParams) -> str:
            """Search for users by query string with pagination.

            Use it to find users by email, name, or other text. With a known ID use
            zammad_get_user.

            Args:
                params (SearchUsersParams): Validated search parameters containing:
                    - query (str): Search string (matches name, email, login) (required)
                    - page (int): Page number (default: 1)
                    - per_page (int): Results per page, 1-100 (default: 25)
                    - response_format (ResponseFormat): Output format - markdown or json (default: markdown)

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

                JSON format (abbreviated example; items are full User model dumps and the
                object also has offset, next_offset, and _meta):
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

        @self.mcp.tool(annotations=_write_annotations("Create User"))
        @flat_params(UserCreate)
        def zammad_create_user(params: UserCreate) -> User:
            """Create a new user (customer) in Zammad.

            Search with zammad_search_users first to avoid duplicates. A new user can then be the
            customer of zammad_create_ticket.

            Args:
                params (UserCreate): User creation parameters:
                    - email (str): Email address (required)
                    - firstname (str): First name (required)
                    - lastname (str): Last name (required)
                    - login, phone, mobile, organization, note (optional)

            Returns:
                User: Created user object

            Examples:
                - "Create customer" -> email, firstname, lastname
                - "Add contact with phone" -> + phone field
                - Don't use when: User exists (use zammad_search_users first)

            Note:
                After creating, use their email in zammad_create_ticket's customer field.

            Error Handling:
                - A missing required field or an email without "@" and a dotted domain fails
                  Pydantic validation before any API call
                - Zammad errors (HTTP error text for 401/403/422, including a duplicate email)
                  propagate unchanged; FastMCP returns a tool error with that text
            """
            client = self.get_client()
            user_data = client.create_user(**params.model_dump(exclude_none=True))
            return User(**user_data)

        @self.mcp.tool(annotations=_read_only_annotations("Get Organization Details"))
        @flat_params(GetOrganizationParams)
        def zammad_get_organization(params: GetOrganizationParams) -> str:
            """Get detailed information about a specific organization by ID.

            Use the internal organization ID; to find one by name use zammad_search_organizations.
            Returns the standard organization fields; custom attributes are not included.

            Args:
                params (GetOrganizationParams): Validated parameters containing:
                    - org_id (int): Organization's internal database ID (required)
                    - response_format (ResponseFormat): Output format - markdown (default) or json

            Returns:
                str: Formatted organization information.
                     - Markdown format: name, ID, active, shared, then optional Domain, Members,
                       and Notes sections, and a Metadata section (created, updated)
                     - JSON format: the Organization model (id, name, shared, domain,
                       domain_assignment, active, note, created_by_id, updated_by_id, created_at,
                       updated_at, created_by, updated_by, members). The client call does not
                       request expanded data, so members/created_by/updated_by are usually null
                       unless Zammad returns them. Custom attributes are dropped.

                Abbreviated example JSON response:
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
                - Zammad errors (HTTP error text for 401/403/404, e.g. unknown org_id)
                  propagate unchanged; FastMCP returns a tool error with that text

            Note:
                Returns the standard Organization model fields only; custom attributes are
                not included.
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
        @flat_params(SearchOrganizationsParams)
        def zammad_search_organizations(params: SearchOrganizationsParams) -> str:
            """Search for organizations by query string with pagination.

            Use it to find organizations by name or other text. With a known ID use
            zammad_get_organization.

            Args:
                params (SearchOrganizationsParams): Validated search parameters containing:
                    - query (str): Search string (matches name, domain, note) (required)
                    - page (int): Page number (default: 1)
                    - per_page (int): Results per page, 1-100 (default: 25)
                    - response_format (ResponseFormat): Output format - markdown or json (default: markdown)

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

                JSON format (abbreviated example; items are full Organization model dumps and
                the object also has offset, next_offset, and _meta):
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

            Use it to check which Zammad account the server's configured credentials belong to.
            The result is a User object with fields such as id, login, firstname, lastname,
            email, organization_id, and active. For another user use zammad_get_user or
            zammad_search_users.

            Returns:
                User: The authenticated user.
            """
            client = self.get_client()
            user_data = client.get_current_user()
            return User(**user_data)

    def _get_cached_groups(self) -> list[Group]:
        """Get cached list of groups.

        Zammad filters groups by the caller's permissions, so with OAuth (one identity
        per request) the list is fetched per call instead of shared across users.
        """
        if self.auth_config.enabled:
            return [Group(**group) for group in self.get_client().get_groups()]
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
            Categorizes by the state's state_type_id (seeded and stable), not
            the state name, so a custom state typed as pending still lands in
            the pending bucket:
            - new (1), open (2) -> open
            - closed (5) -> closed
            - pending reminder (3), pending action (4) -> pending
            Any other state (e.g. merged, 6) is counted in the total but not
            in any bucket.
        """
        state_type_mapping = self._get_state_type_mapping()
        state_type_id = state_type_mapping.get(state_name, 0)

        if state_type_id in (STATE_TYPE_NEW, STATE_TYPE_OPEN):
            return (1, 0, 0)
        if state_type_id == STATE_TYPE_CLOSED:
            return (0, 1, 0)
        if state_type_id in (STATE_TYPE_PENDING_REMINDER, STATE_TYPE_PENDING_ACTION):
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
    ) -> tuple[int, int, int, int, int, int, bool]:
        """Collect ticket statistics using pagination.

        Args:
            client: Zammad client instance
            group: Optional group filter

        Returns:
            Tuple of (total, open, closed, pending, escalated, pages, truncated) counts.
            truncated is True when the scan stopped at a backend limit, making the
            counts lower bounds rather than exact totals.
        """
        total_count = 0
        open_count = 0
        closed_count = 0
        pending_count = 0
        escalated_count = 0
        page = 1
        per_page = MAX_PER_PAGE
        truncated = False

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

            # A group filter routes through the search endpoint, which stops returning
            # results at SEARCH_RESULT_CAP. Record that the totals are lower bounds
            # instead of reporting the capped number as exact.
            if group and total_count >= SEARCH_RESULT_CAP:
                truncated = True
                logger.warning(
                    "Group '%s' reached the search result cap (%s); counts are lower bounds, not exact totals",
                    group,
                    SEARCH_RESULT_CAP,
                )
                break

            if page > MAX_PAGES_FOR_TICKET_SCAN:
                truncated = True
                logger.warning(
                    "Reached maximum page limit (%s pages), processed %s tickets - some tickets may not be counted",
                    MAX_PAGES_FOR_TICKET_SCAN,
                    total_count,
                )
                break

        return total_count, open_count, closed_count, pending_count, escalated_count, page - 1, truncated

    def _build_stats_result(
        self,
        total: int,
        open_count: int,
        closed: int,
        pending: int,
        escalated: int,
        pages: int,
        elapsed: float,
        truncated: bool = False,
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
            truncated: Whether the scan stopped at a backend limit

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
            counts_truncated=truncated,
        )

    def _setup_system_tools(self) -> None:  # noqa: PLR0915
        """Register system information tools."""

        @self.mcp.tool(annotations=_read_only_annotations("Get Ticket Statistics"))
        @flat_params(GetTicketStatsParams)
        def zammad_get_ticket_stats(params: GetTicketStatsParams) -> TicketStats:
            """Get aggregated ticket statistics with counts by state.

            Scans matching tickets page by page, so it can be slow on large instances;
            counts_truncated is true when the scan hit its limit. An unknown group name returns
            zero counts, not an error; check names with zammad_list_groups.

            Args:
                params (GetTicketStatsParams): Validated parameters containing:
                    - group (str | None): Filter by group name
                    - start_date (date | datetime | None): Start date filter (not yet implemented)
                    - end_date (date | datetime | None): End date filter (not yet implemented;
                      must not be before start_date)

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
                    "avg_resolution_time": null,
                    "counts_truncated": false
                }
                ```

            Examples:
                - Use when: "Show ticket statistics" -> no parameters
                - Use when: "Stats for Support group" -> group="Support"
                - Use when: "How many escalated tickets?" -> check escalated_count
                - Don't use when: Need individual ticket details (use zammad_search_tickets)
                - Don't use when: Need real-time counts (this scans all tickets via pagination)

            Error Handling:
                - Sets counts_truncated=true (and logs a warning) when the scan stops at the
                  1000-page limit or a group-filtered scan reaches the 10,000-result search cap
                - An unknown group name returns zero counts, not an error (the search matches
                  nothing)
                - Zammad errors (HTTP error text for 401/403) propagate unchanged; FastMCP
                  returns a tool error with that text

            Note:
                Uses pagination to scan tickets without loading all into memory.
                May take several seconds for large ticket databases (>10k tickets).
                State categorization is by state_type_id: new(1)/open(2)=open,
                closed(5)=closed, pending reminder(3)/pending action(4)=pending.
                Date filtering (start_date, end_date) not yet implemented - shows warning if provided.
                Processes up to 100,000 tickets (1000 pages x 100 per page).
                counts_truncated is true when the scan stopped early. For a group-filtered
                scan, every count is then a lower bound because the 10,000-result search
                cap was reached.
            """
            start_time = time.time()
            client = self.get_client()

            if params.start_date or params.end_date:
                logger.warning("Date filtering not yet implemented - ignoring date parameters")

            group_filter_msg = f" for group '{params.group}'" if params.group else ""
            logger.info("Starting ticket statistics calculation%s", group_filter_msg)

            total, open_count, closed, pending, escalated, pages, truncated = self._collect_ticket_stats_paginated(
                client, params.group
            )

            return self._build_stats_result(
                total, open_count, closed, pending, escalated, pages, time.time() - start_time, truncated
            )

        @self.mcp.tool(annotations=_read_only_annotations("List Groups"))
        @flat_params(ListParams)
        def zammad_list_groups(params: ListParams) -> str:
            """Get complete list of all available groups (cached).

            List all groups instead of searching. Group names work
            in zammad_create_ticket, zammad_update_ticket, and zammad_search_tickets.

            Args:
                params (ListParams): Validated parameters containing:
                    - response_format (ResponseFormat): Output format - markdown or json (default: markdown)

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

                JSON format (abbreviated example; the object also has offset, next_page, next_offset, and _meta):
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
                - Zammad errors (HTTP error text for 401/403) propagate unchanged on the first,
                  uncached call; FastMCP returns a tool error with that text

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
        @flat_params(ListParams)
        def zammad_list_ticket_states(params: ListParams) -> str:
            """Get complete list of all available ticket states (cached).

            List all states instead of searching. State names work
            in zammad_create_ticket, zammad_update_ticket, and zammad_search_tickets.

            Args:
                params (ListParams): Validated parameters containing:
                    - response_format (ResponseFormat): Output format - markdown or json (default: markdown)

            Returns:
                str: Formatted response with the following schema:

                Markdown format (default):
                ```
                # Ticket State List

                Found N ticket state(s)

                - **new** (ID: 1)
                - **open** (ID: 2)
                - **pending reminder** (ID: 3)
                - **closed** (ID: 5)
                ```

                JSON format (abbreviated example; the object also has offset, next_page, next_offset, and _meta):
                ```json
                {
                    "items": [
                        {"id": 1, "name": "new", "state_type_id": 1},
                        {"id": 2, "name": "open", "state_type_id": 2},
                        {"id": 3, "name": "pending reminder", "state_type_id": 3},
                        {"id": 5, "name": "closed", "state_type_id": 5}
                    ],
                    "total": 4,
                    "count": 4,
                    "page": 1,
                    "per_page": 4,
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
                - Zammad errors (HTTP error text for 401/403) propagate unchanged on the first,
                  uncached call; FastMCP returns a tool error with that text

            Note:
                Results are cached in memory for performance (cleared on server restart).
                All states are returned in a single response (no pagination needed).
                Use state 'name' field when creating/updating tickets, not ID.
                Built-in state_type_id values are seeded and stable across
                Zammad installations (new=1, open=2, pending reminder=3,
                pending action=4, closed=5, merged=6); custom states may add
                further states that reuse these type ids.
            """
            states = self._get_cached_states()

            # Format response
            if params.response_format == ResponseFormat.JSON:
                result = _format_list_json(states)
            else:
                result = _format_list_markdown(states, "Ticket State")

            return truncate_response(result)

        @self.mcp.tool(annotations=_read_only_annotations("List Ticket Priorities"))
        @flat_params(ListParams)
        def zammad_list_ticket_priorities(params: ListParams) -> str:
            """Get complete list of all available ticket priorities (cached).

            List all priorities instead of searching. Priority
            names work in zammad_create_ticket, zammad_update_ticket, and zammad_search_tickets.

            Args:
                params (ListParams): Validated parameters containing:
                    - response_format (ResponseFormat): Output format - markdown or json (default: markdown)

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

                JSON format (abbreviated example; the object also has offset, next_page, next_offset, and _meta):
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
                - Zammad errors (HTTP error text for 401/403) propagate unchanged on the first,
                  uncached call; FastMCP returns a tool error with that text

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

        @self.mcp.tool(annotations=_read_only_annotations("List Tags"))
        @flat_params(ListParams)
        def zammad_list_tags(params: ListParams) -> str:
            """Get all tags defined in the Zammad system.

            Requires the admin.tag permission, which regular agents do not have. For the tags of
            one ticket use zammad_get_ticket_tags.

            Args:
                params (ListParams): Validated parameters containing:
                    - response_format (ResponseFormat): Output format - markdown or json (default: markdown)

            Returns:
                str: Formatted response with the following schema:

                Markdown format (default):
                ```
                # Tag List

                Found N tag(s)

                - **urgent** (ID: 1, used 15 times)
                - **billing** (ID: 2, used 8 times)
                - **feature-request** (ID: 3, used 23 times)
                ```

                JSON format (abbreviated example; the object also has offset, next_page, next_offset, and _meta):
                ```json
                {
                    "items": [
                        {"id": 1, "name": "urgent", "count": 15},
                        {"id": 2, "name": "billing", "count": 8},
                        {"id": 3, "name": "feature-request", "count": 23}
                    ],
                    "total": 3,
                    "count": 3,
                    "page": 1,
                    "per_page": 3,
                    "has_more": false
                }
                ```

            Examples:
                - Use when: "List all available tags" -> get tag vocabulary
                - Use when: "What tags can I use?" -> get valid tag names
                - Use when: "Show me tag options for categorizing tickets"
                - Don't use when: Getting tags for a specific ticket (use zammad_get_ticket_tags)

            Error Handling:
                - Raises requests.HTTPError (403 Forbidden) when the user lacks admin.tag
                  permission, or for 401; FastMCP returns a tool error with that text
                - Returns empty list if no tags defined in system

            Note:
                Requires admin.tag permission (not available to regular agents).
                The 'count' field shows how many tickets use each tag.
                Use tag 'name' field when adding tags to tickets.
            """
            client = self.get_client()
            tags = sorted(client.list_tags(), key=lambda tag: (str(tag.get("name", "")).lower(), tag.get("id", 0)))
            total = len(tags)

            # Format response
            if params.response_format == ResponseFormat.JSON:
                result = json.dumps(
                    {
                        "items": tags,
                        "total": total,
                        "count": total,
                        "page": 1,
                        "per_page": total,
                        "offset": 0,
                        "has_more": False,
                        "next_page": None,
                        "next_offset": None,
                        "_meta": {},
                    },
                    indent=2,
                    default=str,
                )
            else:
                lines = ["# Tag List", "", f"Found {total} tag(s)", ""]
                for tag in tags:
                    name = tag.get("name", "Unknown")
                    tag_id = tag.get("id", "?")
                    count = tag.get("count", 0)
                    lines.append(f"- **{name}** (ID: {tag_id}, used {count} times)")
                result = "\n".join(lines)

            return truncate_response(result)

        @self.mcp.tool(annotations=_read_only_annotations("Get Ticket Tags"))
        @flat_params(GetTicketTagsParams)
        def zammad_get_ticket_tags(params: GetTicketTagsParams) -> str:
            """Get tags assigned to a specific ticket.

            Use the internal ticket ID. To list every tag in the system use zammad_list_tags.

            Args:
                params (GetTicketTagsParams): Validated parameters containing:
                    - ticket_id (int): Ticket ID to get tags for
                    - response_format (ResponseFormat): Output format - markdown or json (default: markdown)

            Returns:
                str: Formatted response with the following schema:

                Markdown format (default):
                ```
                ## Tags for Ticket #123

                - urgent
                - billing
                - follow-up
                ```

                Or if no tags:
                ```
                Ticket #123 has no tags.
                ```

                JSON format:
                ```json
                {
                    "ticket_id": 123,
                    "tags": ["urgent", "billing", "follow-up"],
                    "count": 3
                }
                ```

            Examples:
                - Use when: "What tags are on ticket 123?" -> ticket_id=123
                - Use when: "Show tags for this ticket" -> ticket_id from context
                - Use when: "Is ticket 456 tagged as urgent?" -> get tags, check list
                - Don't use when: Listing all system tags (use zammad_list_tags)
                - Don't use when: Adding/removing tags (use zammad_add_ticket_tag/zammad_remove_ticket_tag)

            Error Handling:
                - Raises TicketIdGuidanceError (via _handle_ticket_not_found_error) when a
                  request error or ValueError says the ticket was not found
                - Any other exception (Zammad HTTP error text for 401/403) propagates
                  unchanged; FastMCP returns a tool error with that text

            Note:
                Only returns tag names, not full tag metadata.
                Use zammad_list_tags to see all available tags with usage counts.
            """
            client = self.get_client()
            try:
                tags = client.get_ticket_tags(params.ticket_id)
            except (requests.exceptions.RequestException, ValueError) as e:
                _handle_ticket_not_found_error(params.ticket_id, e)

            # Format response
            if params.response_format == ResponseFormat.JSON:
                result = json.dumps(
                    {
                        "ticket_id": params.ticket_id,
                        "tags": tags,
                        "count": len(tags),
                    },
                    indent=2,
                )
            elif not tags:
                result = f"Ticket #{params.ticket_id} has no tags."
            else:
                lines = [f"## Tags for Ticket #{params.ticket_id}", ""]
                for tag in tags:
                    lines.append(f"- {tag}")
                result = "\n".join(lines)

            return truncate_response(result)

    def _setup_resources(self) -> None:
        """Register all resources with the MCP server."""
        self._setup_ticket_resource()
        self._setup_user_resource()
        self._setup_organization_resource()
        self._setup_queue_resource()
        self._setup_kb_resources()

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
                                *_format_article_attachments(article.attachments, article.id),
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
                # One page only: the count label must not read as a total.
                tickets = client.search_tickets(group=group, per_page=QUEUE_PAGE_SIZE)

                if not tickets:
                    return f"Queue for group '{group}': No tickets found"

                ticket_states: dict[str, list[dict[str, Any]]] = {}
                for ticket in tickets:
                    ticket_states.setdefault(self._extract_state_name(ticket), []).append(ticket)

                lines = [f"Queue for Group: {group}", _queue_count_label(len(tickets)), ""]
                for state, state_tickets in sorted(ticket_states.items()):
                    lines.extend(_format_queue_state(state, state_tickets))

                return truncate_response("\n".join(lines))
            except (requests.exceptions.RequestException, ValueError, ValidationError) as e:
                return _handle_api_error(e, context=f"retrieving queue for group '{group}'")

    def _setup_kb_tools(self) -> None:
        """Register read-only Knowledge Base tools.

        Failure semantics: client-level errors (network/HTTP) are propagated as
        exceptions (e.g. ZammadAPIError) so MCP surfaces them as
        actual tool errors instead of returning successful string payloads.
        """
        self._setup_kb_info_tools()
        self._setup_kb_category_tools()
        self._setup_kb_answer_read_tools()

    def _setup_kb_info_tools(self) -> None:
        """Register KB list/get knowledge-base tools."""

        @self.mcp.tool(annotations=_read_only_annotations("List Knowledge Bases"))
        @flat_params(ListKnowledgeBasesParams)
        def zammad_list_knowledge_bases(params: ListKnowledgeBasesParams) -> str:
            """List all knowledge bases available in Zammad.

            Errors (auth, network, HTTP 5xx, ...) are raised as
            ZammadAPIError so the MCP client sees a real tool error.

            Note:
                Requires knowledge_base.reader or knowledge_base.editor permission.
            """
            client = self.get_client()
            kbs = client.list_knowledge_bases()
            if params.response_format == ResponseFormat.JSON:
                result = json.dumps({"items": kbs, "count": len(kbs)}, indent=2, default=str)
            else:
                lines = ["# Knowledge Bases", "", f"Found {len(kbs)} knowledge base(s)", ""]
                for kb in kbs:
                    lines.append(f"## KB ID: {kb.get('id', 'N/A')}")
                    lines.append(f"- **Active**: {kb.get('active', False)}")
                    if kb.get("custom_address"):
                        lines.append(f"- **Address**: {kb['custom_address']}")
                    cat_ids = kb.get("category_ids") or []
                    lines.append(f"- **Root Categories**: {len(cat_ids)}")
                    lines.append("")
                result = "\n".join(lines)
            return truncate_response(result)

        @self.mcp.tool(annotations=_read_only_annotations("Get Knowledge Base"))
        @flat_params(GetKnowledgeBaseParams)
        def zammad_get_knowledge_base(params: GetKnowledgeBaseParams) -> str:
            """Get details of a specific knowledge base by ID.

            Note:
                Requires knowledge_base.reader or knowledge_base.editor permission.
                Use ``zammad_list_knowledge_bases`` to discover available KB IDs.
            """
            client = self.get_client()
            kb = client.get_knowledge_base(params.kb_id)
            if params.response_format == ResponseFormat.JSON:
                result = json.dumps(kb, indent=2, default=str)
            else:
                result = _format_kb_markdown(kb)
            return truncate_response(result)

    def _setup_kb_category_tools(self) -> None:
        """Register read-only KB category tools."""

        @self.mcp.tool(annotations=_read_only_annotations("Get KB Category"))
        @flat_params(GetKBCategoryParams)
        def zammad_get_kb_category(params: GetKBCategoryParams) -> str:
            """Get a knowledge base category by ID.

            Note:
                Requires knowledge_base.reader or knowledge_base.editor permission.
            """
            client = self.get_client()
            category = client.get_kb_category(params.kb_id, params.category_id)
            if params.response_format == ResponseFormat.JSON:
                result = json.dumps(category, indent=2, default=str)
            else:
                result = _format_kb_category_markdown(category)
            return truncate_response(result)

    def _setup_kb_answer_read_tools(self) -> None:
        """Register read-only KB answer tools (list/search/get)."""

        @self.mcp.tool(annotations=_read_only_annotations("List KB Answers"))
        @flat_params(ListKBAnswersParams)
        def zammad_list_kb_answers(params: ListKBAnswersParams) -> str:
            """List answers within a KB category.

            Each item has the resolved title in _title and the plain-text body in _body. Requires
            knowledge_base.reader or knowledge_base.editor permission.
            """
            client = self.get_client()
            answers = client.list_kb_answers(params.kb_id, params.category_id)
            if params.response_format == ResponseFormat.JSON:
                result = json.dumps({"items": answers, "count": len(answers)}, indent=2, default=str)
            else:
                result = _format_kb_answers_list_markdown(answers, params.kb_id, params.category_id)
            return truncate_response(result)

        @self.mcp.tool(annotations=_read_only_annotations("Search KB Answers"))
        @flat_params(SearchKBAnswersParams)
        def zammad_search_kb_answers(params: SearchKBAnswersParams) -> str:
            """Case-insensitive substring search of KB answers (title and body).

            Each result also carries its _category_id. Requires knowledge_base.reader or
            knowledge_base.editor permission.

            Searches across all root categories of the KB by default, or only
            the given ``category_id`` and its descendants when provided.
            """
            client = self.get_client()
            results = client.search_kb_answers(params.kb_id, params.query, category_id=params.category_id)
            if params.response_format == ResponseFormat.JSON:
                result = json.dumps(
                    {"items": results, "count": len(results), "query": params.query},
                    indent=2,
                    default=str,
                )
            else:
                result = _format_kb_search_results_markdown(results, params.query, params.kb_id)
            return truncate_response(result)

        @self.mcp.tool(annotations=_read_only_annotations("Get KB Answer"))
        @flat_params(GetKBAnswerParams)
        def zammad_get_kb_answer(params: GetKBAnswerParams) -> str:
            """Get a knowledge base answer by ID, including resolved title and body.

            Requires knowledge_base.reader or knowledge_base.editor permission. Find answer IDs
            with zammad_list_kb_answers or zammad_search_kb_answers.
            """
            client = self.get_client()
            result_payload = client.get_kb_answer_with_content(params.kb_id, params.answer_id)
            answer = result_payload["answer"]
            title = result_payload["title"]
            body = result_payload["body"]
            if params.response_format == ResponseFormat.JSON:
                result = json.dumps(
                    {"answer": answer, "title": title, "body": body},
                    indent=2,
                    default=str,
                )
            else:
                body_truncated = truncate_response(body) if body else ""
                result = _format_kb_answer_markdown(answer, title=title, body=body_truncated)
            return result

    def _setup_kb_resources(self) -> None:
        """Register read-only Knowledge Base resources."""

        @self.mcp.resource("zammad://kb/{kb_id}")
        def get_kb_resource(kb_id: str) -> str:
            """Get a knowledge base as a resource."""
            client = self.get_client()
            kb = client.get_knowledge_base(int(kb_id))
            return truncate_response(_format_kb_markdown(kb))

        @self.mcp.resource("zammad://kb/{kb_id}/category/{category_id}")
        def get_kb_category_resource(kb_id: str, category_id: str) -> str:
            """Get a KB category as a resource."""
            client = self.get_client()
            category = client.get_kb_category(int(kb_id), int(category_id))
            return truncate_response(_format_kb_category_markdown(category))

        @self.mcp.resource("zammad://kb/{kb_id}/answer/{answer_id}")
        def get_kb_answer_resource(kb_id: str, answer_id: str) -> str:
            """Get a KB answer as a resource."""
            client = self.get_client()
            result = client.get_kb_answer_with_content(int(kb_id), int(answer_id))
            body = truncate_response(result["body"]) if result["body"] else ""
            return _format_kb_answer_markdown(result["answer"], title=result["title"], body=body)

    def _setup_prompts(self) -> None:
        """Register all prompts with the MCP server."""

        @self.mcp.prompt()
        def analyze_ticket(ticket_id: str) -> str:
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
        def draft_response(ticket_id: str, tone: str = "professional") -> str:
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

zammad_search_tickets has no escalation filter. Use it with the group and state filters
(for example state="open") and response_format="json", then keep the tickets whose
first_response_escalation_at, update_escalation_at, or close_escalation_at field is set.
Check _meta.truncated before you follow next_page. A truncated response drops tickets from
items but keeps has_more and next_page, so following next_page would skip them. If it is true,
lower per_page and restart from page 1. Follow next_page only from a response that is not
truncated, while has_more is true. For each escalated ticket:
1. Ticket number and title
2. Escalation type (first response, update, or close) from the field that is set
3. Time until escalation
4. Current assignee (owner)
5. Recommended action

Organize the results by urgency and provide actionable recommendations."""


# Create the server instance
server = ZammadMCPServer()

# Export the MCP server instance
mcp = server.mcp


# Health check endpoint for HTTP transport
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:  # noqa: ARG001
    """Health check endpoint for HTTP transport.

    Args:
        request: The incoming HTTP request (required by FastMCP).

    Returns:
        JSONResponse with health status.
    """
    return JSONResponse({"status": "healthy", "transport": "http"})


def main() -> None:
    """Run the MCP server."""
    configure_logging()
    mcp.run()
