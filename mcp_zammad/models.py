"""Pydantic models for Zammad entities."""

import html
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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


class TicketCreate(BaseModel):
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


class TicketUpdate(BaseModel):
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


class TicketSearchParams(BaseModel):
    """Ticket search parameters."""

    query: str | None = Field(None, description="Free text search query")
    state: str | None = Field(None, description="Filter by state name")
    priority: str | None = Field(None, description="Filter by priority name")
    group: str | None = Field(None, description="Filter by group name")
    owner: str | None = Field(None, description="Filter by owner login/email")
    customer: str | None = Field(None, description="Filter by customer email")
    page: int = Field(default=1, description="Page number")
    per_page: int = Field(default=25, description="Results per page")


class Attachment(BaseModel):
    """Ticket article attachment information."""

    id: int
    filename: str
    size: int | None = None
    content_type: str | None = None
    created_at: datetime | None = None


class ArticleCreate(BaseModel):
    """Create article request."""

    ticket_id: int = Field(description="Ticket ID to add article to", gt=0)
    body: str = Field(description="Article body content", max_length=100000)
    type: str = Field(default="note", description="Article type (note, email, phone)", max_length=50)
    internal: bool = Field(default=False, description="Whether the article is internal")
    sender: str = Field(default="Agent", description="Sender type (Agent, Customer, System)", max_length=50)

    @field_validator("body")
    @classmethod
    def sanitize_body(cls, v: str) -> str:
        """Escape HTML to prevent XSS attacks."""
        return html.escape(v)


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
