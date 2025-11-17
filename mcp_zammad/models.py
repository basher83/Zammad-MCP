"""Pydantic models for Zammad entities."""

import base64
import html
import os
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class StrictBaseModel(BaseModel):
    """Base model with strict validation that forbids extra fields.

    This ensures that typos or incorrect field names in request parameters
    are caught early with clear validation errors rather than being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")


class ResponseFormat(str, Enum):
    """Output format for tool responses.

    Attributes:
        MARKDOWN: Human-readable markdown format
        JSON: Machine-readable JSON format with full metadata
    """

    MARKDOWN = "markdown"
    JSON = "json"


class ArticleType(str, Enum):
    """Article type enumeration.

    Attributes:
        NOTE: Internal note
        EMAIL: Email communication
        PHONE: Phone call record
    """

    NOTE = "note"
    EMAIL = "email"
    PHONE = "phone"


class ArticleSender(str, Enum):
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
            raise ValueError(f"Invalid base64 encoding: {e}") from e
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


class Ticket(BaseModel):
    """Zammad ticket."""

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
        """Escape HTML to prevent XSS attacks."""
        return html.escape(v)


class TicketUpdate(StrictBaseModel):
    """Update ticket request."""

    title: str | None = Field(None, description="New ticket title", max_length=200)
    state: str | None = Field(None, description="New state name", max_length=100)
    priority: str | None = Field(None, description="New priority name", max_length=100)
    owner: str | None = Field(None, description="New owner login/email", max_length=255)
    group: str | None = Field(None, description="New group name", max_length=100)

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str | None) -> str | None:
        """Escape HTML to prevent XSS attacks."""
        return html.escape(v) if v else v


class TicketSearchParams(StrictBaseModel):
    """Ticket search parameters."""

    query: str | None = Field(None, description="Free text search query")
    state: str | None = Field(None, description="Filter by state name")
    priority: str | None = Field(None, description="Filter by priority name")
    group: str | None = Field(None, description="Filter by group name")
    owner: str | None = Field(None, description="Filter by owner login/email")
    customer: str | None = Field(None, description="Filter by customer email")
    page: int = Field(default=1, ge=1, description="Page number (must be >= 1)")
    per_page: int = Field(default=25, ge=1, le=100, description="Results per page (1-100)")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class Attachment(BaseModel):
    """Ticket article attachment information."""

    id: int
    filename: str
    size: int | None = None
    content_type: str | None = None
    created_at: datetime | None = None


class ArticleCreate(StrictBaseModel):
    """Create article request."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    ticket_id: int = Field(description="Ticket ID to add article to", gt=0)
    body: str = Field(description="Article body content", max_length=100000)
    article_type: ArticleType = Field(default=ArticleType.NOTE, alias="type", description="Article type")
    internal: bool = Field(default=False, description="Whether the article is internal")
    sender: ArticleSender = Field(default=ArticleSender.AGENT, description="Sender type")

    @field_validator("body")
    @classmethod
    def sanitize_body(cls, v: str) -> str:
        """Escape HTML to prevent XSS attacks."""
        return html.escape(v)


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

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str | None) -> str | None:
        """Escape HTML to prevent XSS attacks."""
        return html.escape(v) if v else v


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


class TagOperationParams(StrictBaseModel):
    """Tag operation (add/remove) request parameters."""

    ticket_id: int = Field(gt=0, description="Ticket ID")
    tag: str = Field(min_length=1, max_length=100, description="Tag name")


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


class TagOperationResult(BaseModel):
    """Result of a tag operation (add/remove)."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(description="Whether the operation was successful")
    message: str | None = Field(None, description="Optional message about the operation")
