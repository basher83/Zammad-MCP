"""Pydantic models for Zammad entities."""

import base64
import html
import os
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationInfo, field_validator, model_validator


class CaseInsensitiveStrEnum(str, Enum):
    """String enum that resolves members case-insensitively while keeping canonical values."""

    @classmethod
    def _missing_(cls, value: object) -> "CaseInsensitiveStrEnum | None":
        """Return the member matching ``value`` case-insensitively, or None so Enum raises its usual error."""
        if not isinstance(value, str):
            return None
        folded = value.casefold()
        return next((member for member in cls if member.value.casefold() == folded), None)


def _casefold_str(value: Any) -> Any:
    """Lowercase string input so literal validation is case-insensitive; leave other types untouched."""
    return value.casefold() if isinstance(value, str) else value


ContentType = Annotated[Literal["text/plain", "text/html"], BeforeValidator(_casefold_str)]


class StrictBaseModel(BaseModel):
    """Base model with strict validation that forbids extra fields.

    This ensures that typos or incorrect field names in request parameters
    are caught early with clear validation errors rather than being silently ignored.
    String fields are automatically stripped of leading/trailing whitespace.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseFormat(CaseInsensitiveStrEnum):
    """Output format for tool responses.

    Attributes:
        MARKDOWN: Human-readable markdown format
        JSON: Machine-readable JSON format with full metadata
    """

    MARKDOWN = "markdown"
    JSON = "json"


class ArticleType(CaseInsensitiveStrEnum):
    """Article type enumeration.

    Attributes:
        NOTE: Internal note
        EMAIL: Email communication
        PHONE: Phone call record
    """

    NOTE = "note"
    EMAIL = "email"
    PHONE = "phone"


class ArticleSender(CaseInsensitiveStrEnum):
    """Article sender type enumeration.

    Attributes:
        AGENT: Sent by an agent
        CUSTOMER: Sent by a customer
        SYSTEM: System-generated
    """

    AGENT = "Agent"
    CUSTOMER = "Customer"
    SYSTEM = "System"


class AttachmentUpload(StrictBaseModel):
    """Attachment data for upload."""

    filename: str = Field(description="Attachment filename", max_length=255)
    data: str = Field(description="Base64-encoded file content")
    mime_type: str = Field(description="MIME type (e.g., application/pdf)", max_length=100)

    @field_validator("filename")
    @classmethod
    def sanitize_filename(cls, v: str) -> str:
        """Sanitize filename to prevent path traversal."""
        # Remove path components, keep only basename, and remove null bytes
        return os.path.basename(v).replace("\x00", "")

    @field_validator("data")
    @classmethod
    def validate_base64(cls, v: str) -> str:
        """Validate base64 encoding."""
        try:
            base64.b64decode(v, validate=True)
        except Exception as e:
            raise ValueError("Invalid base64 encoding") from e
        else:
            return v


class AttachmentDownloadError(Exception):
    """Exception raised when attachment download fails.

    Attributes:
        ticket_id: The ticket ID
        article_id: The article ID
        attachment_id: The attachment ID
        message: Explanation of the error
    """

    def __init__(
        self,
        ticket_id: int,
        article_id: int,
        attachment_id: int,
        original_error: Exception,
    ) -> None:
        """Initialize the exception with context."""
        self.ticket_id = ticket_id
        self.article_id = article_id
        self.attachment_id = attachment_id
        self.original_error = original_error
        self.message = (
            f"Failed to download attachment {attachment_id} for ticket {ticket_id} "
            f"article {article_id}: {original_error!s}"
        )
        super().__init__(self.message)


class TicketIdGuidanceError(ValueError):
    """Exception raised when ticket is not found to provide ID vs number guidance.

    Attributes:
        ticket_id: The ticket ID that was not found
        message: Explanation with guidance
    """

    def __init__(self, ticket_id: int) -> None:
        """Initialize the exception with helpful guidance."""
        self.ticket_id = ticket_id
        self.message = (
            f"Ticket ID {ticket_id} not found. "
            f"Note: Use the internal 'id' field from search results, not the display 'number'. "
            f"Example: For ticket #65003, search first to find its internal ID."
        )
        super().__init__(self.message)


class UserBrief(BaseModel):
    """Brief user information."""

    id: int
    login: str | None = None
    email: str | None = None
    firstname: str | None = None
    lastname: str | None = None
    active: bool = True


class OrganizationBrief(BaseModel):
    """Brief organization information."""

    id: int
    name: str
    active: bool = True


class GroupBrief(BaseModel):
    """Brief group information."""

    id: int
    name: str
    active: bool = True


class StateBrief(BaseModel):
    """Brief state information."""

    id: int
    name: str
    state_type_id: int
    active: bool = True


class PriorityBrief(BaseModel):
    """Brief priority information."""

    id: int
    name: str
    ui_icon: str | None = None
    ui_color: str | None = None
    active: bool = True


class Attachment(BaseModel):
    """Ticket article attachment information."""

    id: int
    filename: str
    size: int | None = None
    content_type: str | None = None
    created_at: datetime | None = None


class Article(BaseModel):
    """Ticket article (comment/note)."""

    id: int
    ticket_id: int
    type: str = Field(description="Article type (note, email, phone, etc.)")
    sender: str = Field(description="Sender type (Agent, Customer, System)")
    from_: str | None = Field(None, alias="from", description="From email/name")
    to: str | None = None
    cc: str | None = None
    subject: str | None = None
    body: str
    content_type: str = "text/html"
    internal: bool = False
    created_by_id: int
    updated_by_id: int
    created_at: datetime
    updated_at: datetime
    created_by: UserBrief | str | None = None
    updated_by: UserBrief | str | None = None
    attachments: list[Attachment] | None = Field(
        None, description="Files attached to this article; download via zammad_download_attachment using their id"
    )


class Ticket(BaseModel):
    """Zammad ticket.

    Custom object attributes defined in Zammad Admin arrive as additional
    top-level keys and are retained as extra fields.
    """

    model_config = ConfigDict(extra="allow")

    id: int
    number: str
    title: str
    group_id: int
    state_id: int
    priority_id: int
    customer_id: int
    owner_id: int | None = None
    organization_id: int | None = None
    created_by_id: int
    updated_by_id: int
    created_at: datetime
    updated_at: datetime
    pending_time: datetime | None = None
    first_response_at: datetime | None = None
    first_response_escalation_at: datetime | None = None
    first_response_in_min: int | None = None
    first_response_diff_in_min: int | None = None
    close_at: datetime | None = None
    close_escalation_at: datetime | None = None
    close_in_min: int | None = None
    close_diff_in_min: int | None = None
    update_escalation_at: datetime | None = None
    update_in_min: int | None = None
    update_diff_in_min: int | None = None
    last_contact_at: datetime | None = None
    last_contact_agent_at: datetime | None = None
    last_contact_customer_at: datetime | None = None
    last_owner_update_at: datetime | None = None
    article_count: int | None = None

    # Expanded fields - can be either objects or strings when expand=true
    group: GroupBrief | str | None = None
    state: StateBrief | str | None = None
    priority: PriorityBrief | str | None = None
    customer: UserBrief | str | None = None
    owner: UserBrief | str | None = None
    organization: OrganizationBrief | str | None = None
    created_by: UserBrief | str | None = None
    updated_by: UserBrief | str | None = None

    # Articles if included
    articles: list[Article] | None = None

    # Tags if included
    tags: list[str] | None = None


class TicketCreate(StrictBaseModel):
    """Create ticket request."""

    title: str = Field(description="Ticket title/subject", max_length=200)
    group: str = Field(description="Group name or ID", max_length=100)
    customer: str = Field(description="Customer email or ID", max_length=255)
    article_body: str = Field(description="Initial article/comment body", max_length=100000)
    state: str = Field(default="new", description="State name (new, open, pending reminder, etc.)", max_length=100)
    priority: str = Field(default="2 normal", description="Priority name (1 low, 2 normal, 3 high)", max_length=100)
    article_type: str = Field(default="note", description="Article type (note, email, phone)", max_length=50)
    article_internal: bool = Field(default=False, description="Whether the article is internal")

    @field_validator("title", "article_body")
    @classmethod
    def sanitize_html(cls, v: str) -> str:
        """Escape HTML to prevent XSS attacks.

        quote=False: title and the initial article are plain text (no content_type choice here),
        sent/stored verbatim, so quotes and apostrophes must not become &#x27;/&quot; entities.
        """
        return html.escape(v, quote=False)


class TicketUpdate(StrictBaseModel):
    """Update ticket request."""

    title: str | None = Field(None, description="New ticket title", max_length=200)
    state: str | None = Field(None, description="New state name", max_length=100)
    priority: str | None = Field(None, description="New priority name", max_length=100)
    owner: str | None = Field(None, description="New owner login/email", max_length=255)
    group: str | None = Field(None, description="New group name", max_length=100)
    time_unit: float | None = Field(
        None, description="Time spent for time accounting (unit defined in Zammad admin settings)", gt=0
    )

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str | None) -> str | None:
        """Escape HTML to prevent XSS attacks."""
        return html.escape(v, quote=False) if v else v


class TicketSearchParams(StrictBaseModel):
    """Ticket search parameters."""

    query: str | None = Field(None, description="Free text search query")
    state: str | None = Field(None, description="Filter by state name")
    priority: str | None = Field(None, description="Filter by priority name")
    group: str | None = Field(None, description="Filter by group name")
    owner: str | None = Field(None, description="Filter by owner login/email")
    customer: str | None = Field(None, description="Filter by customer email")
    created_after: date | None = Field(None, description="Only tickets created on or after this date (YYYY-MM-DD)")
    created_before: date | None = Field(None, description="Only tickets created on or before this date (YYYY-MM-DD)")
    page: int = Field(default=1, ge=1, description="Page number (must be >= 1)")
    per_page: int = Field(default=25, ge=1, le=100, description="Results per page (1-100)")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")

    @model_validator(mode="after")
    def validate_date_range(self) -> "TicketSearchParams":
        """Reject an inverted date range rather than silently returning nothing."""
        if self.created_after and self.created_before and self.created_after > self.created_before:
            raise ValueError("created_after must not be later than created_before")
        return self


class ArticleCreate(StrictBaseModel):
    """Create article request with optional attachments."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    ticket_id: int = Field(description="Ticket ID to add article to", gt=0)
    body: str = Field(description="Article body content", max_length=100000)
    article_type: ArticleType = Field(default=ArticleType.NOTE, alias="type", description="Article type")
    internal: bool = Field(default=False, description="Whether the article is internal")
    sender: ArticleSender = Field(default=ArticleSender.AGENT, description="Sender type")
    subject: str | None = Field(default=None, max_length=500, description="Email subject")
    to: str | None = Field(default=None, max_length=1000, description="Email recipient")
    cc: str | None = Field(default=None, max_length=1000, description="Email CC recipient(s)")
    content_type: ContentType = Field(default="text/plain", description="Article content type")
    time_unit: float | None = Field(
        default=None, description="Time spent for time accounting (unit defined in Zammad admin settings)", gt=0
    )
    attachments: list[AttachmentUpload] | None = Field(
        default=None, description="Optional attachments to include", max_length=10
    )

    @model_validator(mode="after")
    def sanitize_body(self) -> "ArticleCreate":
        """Sanitize body content according to content type."""
        if self.content_type == "text/plain":
            # quote=False: plain text is sent/stored verbatim (e.g. in outbound emails), so quotes
            # and apostrophes must not be turned into &#x27;/&quot; entities. Still neutralize
            # <, >, & in case a downstream renderer treats the body as HTML despite the content type.
            self.body = html.escape(self.body, quote=False)
        else:
            self.body = self._sanitize_html_body(self.body)
        return self

    @staticmethod
    def _sanitize_html_body(value: str) -> str:
        """Remove high-risk HTML constructs while preserving basic HTML markup."""
        return value.replace("<script", "&lt;script").replace("</script", "&lt;/script").replace("javascript:", "")


class GetTicketParams(StrictBaseModel):
    """Get ticket request parameters."""

    ticket_id: int = Field(gt=0, description="Ticket ID")
    include_articles: bool = Field(default=True, description="Whether to include ticket articles/comments")
    article_limit: int = Field(default=10, ge=-1, description="Maximum number of articles to return (-1 for all)")
    article_offset: int = Field(default=0, ge=0, description="Number of articles to skip for pagination")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: markdown (default) or json"
    )


class TicketUpdateParams(StrictBaseModel):
    """Update ticket request parameters."""

    ticket_id: int = Field(gt=0, description="The ticket ID to update")
    title: str | None = Field(None, description="New ticket title", max_length=200)
    state: str | None = Field(None, description="New state name", max_length=100)
    priority: str | None = Field(None, description="New priority name", max_length=100)
    owner: str | None = Field(None, description="New owner login/email", max_length=255)
    group: str | None = Field(None, description="New group name", max_length=100)
    customer: str | None = Field(None, description="New customer email/login (must exist in Zammad)", max_length=255)
    pending_time: datetime | None = Field(
        None,
        description=(
            "Pending-until timestamp (ISO 8601, e.g. '2026-07-01T08:00:00Z'). "
            "Required by Zammad when state is 'pending reminder' or 'pending close'."
        ),
    )
    time_unit: float | None = Field(
        None, description="Time spent for time accounting (unit defined in Zammad admin settings)", gt=0
    )
    custom_fields: dict[str, Any] | None = Field(
        None,
        description="Custom Zammad object attributes to set, keyed by attribute name (e.g. {'region': 'north'})",
    )

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str | None) -> str | None:
        """Escape HTML-sensitive characters while keeping quotes and apostrophes readable."""
        return html.escape(v, quote=False) if v else v

    @model_validator(mode="after")
    def require_pending_time_for_pending_states(self) -> "TicketUpdateParams":
        """Fail fast when moving to a seeded pending state without a pending_time.

        Only Zammad's seeded state names are checked; custom states are left to
        Zammad's own validation because their names say nothing about their type.
        """
        seeded_pending_states = {"pending reminder", "pending close"}
        if self.state is not None and self.state.lower() in seeded_pending_states and self.pending_time is None:
            raise ValueError(f"state '{self.state}' requires 'pending_time' (the pending-until timestamp, ISO 8601).")
        return self

    @field_validator("custom_fields")
    @classmethod
    def reject_reserved_custom_field_names(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Reject custom field names that are empty or shadow built-in update fields."""
        if v is None:
            return v
        reserved = set(cls.model_fields) - {"custom_fields"}
        for name in v:
            if not name:
                raise ValueError("custom_fields keys must be non-empty attribute names")
            if name in reserved:
                raise ValueError(f"custom_fields key '{name}' is a built-in field; pass it as a top-level parameter")
        return v


# Same bounds as TagOperationParams.tag so bulk and single-tag tools reject the same input.
TagName = Annotated[str, Field(min_length=1, max_length=100)]


class BulkTicketUpdateParams(StrictBaseModel):
    """Bulk ticket update request parameters."""

    ticket_ids: list[int] = Field(
        min_length=1, max_length=100, description="Internal ticket IDs to update (1-100, no duplicates)"
    )
    title: str | None = Field(None, description="New ticket title", max_length=200)
    state: str | None = Field(None, description="New state name", max_length=100)
    priority: str | None = Field(None, description="New priority name", max_length=100)
    owner: str | None = Field(None, description="New owner login/email", max_length=255)
    group: str | None = Field(None, description="New group name", max_length=100)
    time_unit: float | None = Field(None, description="Time spent per ticket for time accounting", gt=0)
    add_tags: list[TagName] | None = Field(None, description="Tags to add to every ticket")
    remove_tags: list[TagName] | None = Field(None, description="Tags to remove from every ticket")
    note: str | None = Field(None, description="Internal note to add to every ticket", max_length=10000)
    delay_seconds: float = Field(0, ge=0, le=10, description="Pause between tickets (max 10s) to reduce API pressure")

    @field_validator("ticket_ids")
    @classmethod
    def validate_ticket_ids(cls, v: list[int]) -> list[int]:
        """Require positive, unique ticket IDs."""
        if any(ticket_id <= 0 for ticket_id in v):
            raise ValueError("ticket_ids must be greater than 0")
        if len(set(v)) != len(v):
            raise ValueError("ticket_ids must be unique")
        return v

    @field_validator("title", "note")
    @classmethod
    def sanitize_text(cls, v: str | None) -> str | None:
        """Escape HTML to prevent XSS attacks."""
        return html.escape(v) if v else v

    @model_validator(mode="after")
    def require_operation(self) -> "BulkTicketUpdateParams":
        """Reject requests that would change nothing."""
        fields = (self.title, self.state, self.priority, self.owner, self.group, self.time_unit, self.note)
        if any(value is not None for value in fields) or self.add_tags or self.remove_tags:
            return self
        raise ValueError("Specify at least one field, tag, or note to apply")


class BulkUpdateFailure(StrictBaseModel):
    """A single ticket that could not be fully updated."""

    ticket_id: int = Field(description="Ticket ID that failed")
    error: str = Field(description="Actionable error message")


class BulkUpdateResult(StrictBaseModel):
    """Outcome of a bulk ticket update."""

    successful_ticket_ids: list[int] = Field(description="Tickets where every requested action succeeded")
    failed: list[BulkUpdateFailure] = Field(description="Tickets that failed with their error")
    total_processed: int = Field(description="Number of tickets attempted")
    total_successful: int = Field(description="Number of tickets fully updated")


class GetArticleAttachmentsParams(StrictBaseModel):
    """Get article attachments request parameters."""

    ticket_id: int = Field(gt=0, description="Ticket ID")
    article_id: int = Field(gt=0, description="Article ID")


class DownloadAttachmentParams(StrictBaseModel):
    """Download attachment request parameters."""

    ticket_id: int = Field(gt=0, description="Ticket ID")
    article_id: int = Field(gt=0, description="Article ID")
    attachment_id: int = Field(gt=0, description="Attachment ID")
    max_bytes: int | None = Field(
        default=10_000_000, ge=1, description="Maximum attachment size in bytes (None for unlimited)"
    )


class TicketMergeParams(StrictBaseModel):
    """Ticket merge request parameters.

    The target may be given by its display number (as shown in the Zammad UI)
    or by its internal ID, but not both.
    """

    source_ticket_id: int = Field(gt=0, description="Internal ID of the ticket to merge (it becomes closed/merged)")
    target_ticket_number: str | None = Field(
        default=None, min_length=1, max_length=100, description="Display number of the ticket to merge into"
    )
    target_ticket_id: int | None = Field(
        default=None, gt=0, description="Internal ID of the ticket to merge into (alternative to number)"
    )

    @model_validator(mode="after")
    def require_exactly_one_target(self) -> "TicketMergeParams":
        """Ensure exactly one target identifier is supplied."""
        provided = [v for v in (self.target_ticket_number, self.target_ticket_id) if v is not None]
        if len(provided) != 1:
            msg = "Provide exactly one of target_ticket_number or target_ticket_id"
            raise ValueError(msg)
        return self


class TicketMergeResult(StrictBaseModel):
    """Result of a ticket merge operation."""

    result: str = Field(description="Zammad merge result, 'success' when the merge completed")
    target_ticket: Ticket = Field(description="The surviving target ticket after the merge")


class TagOperationParams(StrictBaseModel):
    """Tag operation (add/remove) request parameters."""

    ticket_id: int = Field(gt=0, description="Ticket ID")
    tag: str = Field(min_length=1, max_length=100, description="Tag name")


class GetTicketTagsParams(StrictBaseModel):
    """Get ticket tags request parameters."""

    ticket_id: int = Field(gt=0, description="Ticket ID")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: markdown (default) or json"
    )


class GetUserParams(StrictBaseModel):
    """Get user request parameters."""

    user_id: int = Field(gt=0, description="User ID")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: markdown (default) or json"
    )


class SearchUsersParams(StrictBaseModel):
    """Search users request parameters."""

    query: str = Field(min_length=1, description="Search query (name, email, etc.)")
    page: int = Field(default=1, ge=1, description="Page number (must be >= 1)")
    per_page: int = Field(default=25, ge=1, le=100, description="Results per page (1-100)")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetOrganizationParams(StrictBaseModel):
    """Get organization request parameters."""

    org_id: int = Field(gt=0, description="Organization ID")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN, description="Output format: markdown (default) or json"
    )


class SearchOrganizationsParams(StrictBaseModel):
    """Search organizations request parameters."""

    query: str = Field(min_length=1, description="Search query (name, domain, etc.)")
    page: int = Field(default=1, ge=1, description="Page number (must be >= 1)")
    per_page: int = Field(default=25, ge=1, le=100, description="Results per page (1-100)")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetTicketStatsParams(StrictBaseModel):
    """Get ticket statistics request parameters."""

    group: str | None = Field(None, description="Filter by group name")
    start_date: date | datetime | None = Field(
        None, description="Start date for filtering tickets (ISO format: YYYY-MM-DD) - NOT YET IMPLEMENTED"
    )
    end_date: date | datetime | None = Field(
        None, description="End date for filtering tickets (ISO format: YYYY-MM-DD) - NOT YET IMPLEMENTED"
    )

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: date | datetime | None, info: ValidationInfo) -> date | datetime | None:
        """Validate that end_date is not before start_date.

        TODO: This validation is currently a placeholder since date filtering
        is not yet implemented in the backend. Once implemented, this will
        ensure end_date >= start_date.
        """
        if v is not None and info.data.get("start_date") is not None:
            start = info.data["start_date"]
            # Convert datetime to date for comparison if needed
            start_date = start.date() if isinstance(start, datetime) else start
            end_date = v.date() if isinstance(v, datetime) else v
            if end_date < start_date:
                raise ValueError("end_date must be greater than or equal to start_date")
        return v


class ListParams(StrictBaseModel):
    """List resource request parameters."""

    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class User(BaseModel):
    """Full user information."""

    id: int
    organization_id: int | None = None
    login: str | None = None
    email: str | None = None
    firstname: str | None = None
    lastname: str | None = None
    image: str | None = None
    image_source: str | None = None
    web: str | None = None
    phone: str | None = None
    fax: str | None = None
    mobile: str | None = None
    department: str | None = None
    street: str | None = None
    zip: str | None = None
    city: str | None = None
    country: str | None = None
    address: str | None = None
    vip: bool = False
    verified: bool = False
    active: bool = True
    note: str | None = None
    last_login: datetime | None = None
    out_of_office: bool = False
    out_of_office_start_at: datetime | None = None
    out_of_office_end_at: datetime | None = None
    out_of_office_replacement_id: int | None = None
    created_by_id: int | None = None
    updated_by_id: int | None = None
    created_at: datetime
    updated_at: datetime

    # Expanded fields - can be either objects or strings when expand=true
    organization: OrganizationBrief | str | None = None
    created_by: UserBrief | str | None = None
    updated_by: UserBrief | str | None = None


class UserCreate(StrictBaseModel):
    """Create user request."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    email: str = Field(description="User email (required)", max_length=255)
    firstname: str = Field(description="First name", max_length=100)
    lastname: str = Field(description="Last name", max_length=100)
    login: str | None = Field(None, description="Login username", max_length=255)
    phone: str | None = Field(None, description="Phone number", max_length=100)
    mobile: str | None = Field(None, description="Mobile number", max_length=100)
    organization: str | None = Field(None, description="Organization name", max_length=255)
    note: str | None = Field(None, description="Internal notes", max_length=5000)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError(f"Invalid email: '{v}'. Example: user@example.com")
        local_part, domain = v.rsplit("@", 1)
        if not local_part or not domain or "." not in domain:
            raise ValueError(f"Invalid email: '{v}'. Example: user@example.com")
        return v.lower()

    @field_validator("firstname", "lastname")
    @classmethod
    def sanitize_names(cls, v: str) -> str:
        return html.escape(v)


class Organization(BaseModel):
    """Organization information."""

    id: int
    name: str
    shared: bool = True
    domain: str | None = None
    domain_assignment: bool = False
    active: bool = True
    note: str | None = None
    created_by_id: int | None = None
    updated_by_id: int | None = None
    created_at: datetime
    updated_at: datetime

    # Expanded fields - can be either objects or strings when expand=true
    created_by: UserBrief | str | None = None
    updated_by: UserBrief | str | None = None
    members: list[UserBrief | str] | None = None


class Group(BaseModel):
    """Group information."""

    id: int
    name: str
    assignment_timeout: int | None = None
    follow_up_possible: str = "yes"
    follow_up_assignment: bool = True
    email_address_id: int | None = None
    signature_id: int | None = None
    note: str | None = None
    active: bool = True
    created_by_id: int | None = None
    updated_by_id: int | None = None
    created_at: datetime
    updated_at: datetime


class TicketState(BaseModel):
    """Ticket state information."""

    id: int
    name: str
    state_type_id: int
    next_state_id: int | None = None
    ignore_escalation: bool = False
    default_create: bool = False
    default_follow_up: bool = False
    note: str | None = None
    active: bool = True
    created_by_id: int | None = None
    updated_by_id: int | None = None
    created_at: datetime
    updated_at: datetime


class TicketPriority(BaseModel):
    """Ticket priority information."""

    id: int
    name: str
    default_create: bool = False
    ui_icon: str | None = None
    ui_color: str | None = None
    note: str | None = None
    active: bool = True
    created_by_id: int | None = None
    updated_by_id: int | None = None
    created_at: datetime
    updated_at: datetime


class TicketStats(BaseModel):
    """Ticket statistics."""

    total_count: int = Field(description="Total number of tickets")
    open_count: int = Field(description="Number of open tickets")
    closed_count: int = Field(description="Number of closed tickets")
    pending_count: int = Field(description="Number of pending tickets")
    escalated_count: int = Field(description="Number of escalated tickets")
    avg_first_response_time: float | None = Field(None, description="Average first response time in minutes")
    avg_resolution_time: float | None = Field(None, description="Average resolution time in minutes")
    counts_truncated: bool = Field(
        default=False,
        description=(
            "True when the scan hit the search backend's result cap, so the counts are "
            "lower bounds rather than exact totals."
        ),
    )


class TicketExportParams(StrictBaseModel):
    """Parameters for bulk ticket export to JSONL."""

    output_path: str = Field(description="Path to output JSONL file (must end in .jsonl)")
    query: str | None = Field(None, description="Free text search filter")
    group: str | None = Field(None, description="Filter by group name")
    state: str | None = Field(None, description="Filter by state name")
    created_after: date | None = Field(None, description="Filter tickets created on or after this date (YYYY-MM-DD)")
    created_before: date | None = Field(None, description="Filter tickets created on or before this date (YYYY-MM-DD)")
    delay_seconds: float = Field(default=0.5, ge=0.0, le=10.0, description="Delay between API calls in seconds")
    per_page: int = Field(default=50, ge=1, le=100, description="Number of tickets per page/batch")
    include_internal_articles: bool = Field(default=False, description="Include internal notes in export")
    resume_from_page: int = Field(default=1, ge=1, description="Page to resume export from (for interrupted exports)")
    max_tickets: int | None = Field(default=None, ge=1, description="Maximum number of tickets to export")
    include_tags: bool = Field(
        default=False,
        description="Fetch tags for each ticket. Tags are not part of the ticket payload, "
        "so this costs one extra API call per ticket.",
    )

    @field_validator("output_path")
    @classmethod
    def validate_output_path(cls, v: str) -> str:
        """Validate that output path ends with .jsonl."""
        if not v.endswith(".jsonl"):
            raise ValueError("output_path must end with .jsonl")
        return v


class TagOperationResult(BaseModel):
    """Result of a tag operation (add/remove)."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(description="Whether the operation was successful")
    message: str | None = Field(None, description="Optional message about the operation")


# --- KB read-only param models (StrictBaseModel) ---


class GetKnowledgeBaseParams(StrictBaseModel):
    """Parameters for retrieving a single knowledge base."""

    kb_id: int = Field(gt=0, description="Knowledge base ID")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class ListKnowledgeBasesParams(StrictBaseModel):
    """Parameters for listing knowledge bases."""

    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetKBCategoryParams(StrictBaseModel):
    """Parameters for retrieving a KB category."""

    kb_id: int = Field(gt=0, description="Knowledge base ID")
    category_id: int = Field(gt=0, description="Category ID")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetKBAnswerParams(StrictBaseModel):
    """Parameters for retrieving a KB answer."""

    kb_id: int = Field(gt=0, description="Knowledge base ID")
    answer_id: int = Field(gt=0, description="Answer ID")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class ListKBAnswersParams(StrictBaseModel):
    """Parameters for listing answers within a KB category."""

    kb_id: int = Field(gt=0, description="Knowledge base ID")
    category_id: int = Field(gt=0, description="Category ID")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class SearchKBAnswersParams(StrictBaseModel):
    """Parameters for searching KB answers by title or body keyword."""

    kb_id: int = Field(gt=0, description="Knowledge base ID")
    query: str = Field(
        min_length=1,
        max_length=200,
        description="Search string (case-insensitive substring match on title and body)",
    )
    category_id: int | None = Field(
        default=None,
        gt=0,
        description="Limit search to this category and its descendants (optional)",
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")
