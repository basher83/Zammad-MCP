"""Zammad MCP Server implementation."""

import base64
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .client import ZammadClient
from .models import (
    Article,
    Attachment,
    Group,
    Organization,
    Ticket,
    TicketPriority,
    TicketState,
    TicketStats,
    User,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MAX_TICKETS_FOR_MEMORY_SCAN = 1000
MAX_TICKETS_PER_STATE_IN_QUEUE = 10


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
            logger.info(f"Loaded environment from {cwd_env}")

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
            logger.info(f"Connected as: {current_user.get('email', 'Unknown')}")
        except Exception:
            logger.exception("Failed to initialize Zammad client")
            raise

    def _setup_tools(self) -> None:
        """Register all tools with the MCP server."""
        self._setup_ticket_tools()
        self._setup_user_org_tools()
        self._setup_system_tools()

    def _setup_ticket_tools(self) -> None:
        """Register ticket-related tools."""

        @self.mcp.tool()
        def search_tickets(
            query: str | None = None,
            state: str | None = None,
            priority: str | None = None,
            group: str | None = None,
            owner: str | None = None,
            customer: str | None = None,
            page: int = 1,
            per_page: int = 25,
        ) -> list[Ticket]:
            """Search for tickets with various filters.

            Args:
                query: Free text search query
                state: Filter by state (new, open, closed, etc.)
                priority: Filter by priority (1 low, 2 normal, 3 high)
                group: Filter by group name
                owner: Filter by owner login/email
                customer: Filter by customer email
                page: Page number (default: 1)
                per_page: Results per page (default: 25)

            Returns:
                List of tickets matching the search criteria
            """
            client = self.get_client()
            tickets_data = client.search_tickets(
                query=query,
                state=state,
                priority=priority,
                group=group,
                owner=owner,
                customer=customer,
                page=page,
                per_page=per_page,
            )

            return [Ticket(**ticket) for ticket in tickets_data]

        @self.mcp.tool()
        def get_ticket(
            ticket_id: int, include_articles: bool = True, article_limit: int = 10, article_offset: int = 0
        ) -> Ticket:
            """Get detailed information about a specific ticket.

            Args:
                ticket_id: The ticket ID
                include_articles: Whether to include ticket articles/comments
                article_limit: Maximum number of articles to return (default: 10, use -1 for all)
                article_offset: Number of articles to skip (for pagination, default: 0)

            Returns:
                Ticket details including articles if requested

            Note: Large tickets with many articles may exceed token limits. Use article_limit
            to control the response size. Articles are returned in chronological order.
            """
            client = self.get_client()
            ticket_data = client.get_ticket(ticket_id, include_articles, article_limit, article_offset)
            return Ticket(**ticket_data)

        @self.mcp.tool()
        def create_ticket(
            title: str,
            group: str,
            customer: str,
            article_body: str,
            state: str = "new",
            priority: str = "2 normal",
            article_type: str = "note",
            article_internal: bool = False,
        ) -> Ticket:
            """Create a new ticket in Zammad.

            Args:
                title: Ticket title/subject
                group: Group name or ID
                customer: Customer email or ID
                article_body: Initial article/comment body
                state: State name (default: new)
                priority: Priority name (default: 2 normal)
                article_type: Article type (default: note)
                article_internal: Whether article is internal (default: False)

            Returns:
                The created ticket
            """
            client = self.get_client()
            ticket_data = client.create_ticket(
                title=title,
                group=group,
                customer=customer,
                article_body=article_body,
                state=state,
                priority=priority,
                article_type=article_type,
                article_internal=article_internal,
            )

            return Ticket(**ticket_data)

        @self.mcp.tool()
        def update_ticket(
            ticket_id: int,
            title: str | None = None,
            state: str | None = None,
            priority: str | None = None,
            owner: str | None = None,
            group: str | None = None,
        ) -> Ticket:
            """Update an existing ticket.

            Args:
                ticket_id: The ticket ID to update
                title: New ticket title
                state: New state name
                priority: New priority name
                owner: New owner login/email
                group: New group name

            Returns:
                The updated ticket
            """
            client = self.get_client()
            ticket_data = client.update_ticket(
                ticket_id=ticket_id,
                title=title,
                state=state,
                priority=priority,
                owner=owner,
                group=group,
            )

            return Ticket(**ticket_data)

        @self.mcp.tool()
        def add_article(
            ticket_id: int,
            body: str,
            article_type: str = "note",
            internal: bool = False,
            sender: str = "Agent",
        ) -> Article:
            """Add an article (comment/note) to a ticket.

            Args:
                ticket_id: The ticket ID to add article to
                body: Article body content
                article_type: Article type (note, email, phone)
                internal: Whether article is internal
                sender: Sender type (Agent, Customer, System)

            Returns:
                The created article
            """
            client = self.get_client()
            article_data = client.add_article(
                ticket_id=ticket_id,
                body=body,
                article_type=article_type,
                internal=internal,
                sender=sender,
            )

            return Article(**article_data)

        @self.mcp.tool()
        def get_article_attachments(ticket_id: int, article_id: int) -> list[Attachment]:
            """Get list of attachments for a ticket article.

            Args:
                ticket_id: The ticket ID
                article_id: The article ID

            Returns:
                List of attachment information
            """
            client = self.get_client()
            attachments_data = client.get_article_attachments(ticket_id, article_id)
            return [Attachment(**attachment) for attachment in attachments_data]

        @self.mcp.tool()
        def download_attachment(ticket_id: int, article_id: int, attachment_id: int) -> str:
            """Download an attachment from a ticket article.

            Args:
                ticket_id: The ticket ID
                article_id: The article ID
                attachment_id: The attachment ID

            Returns:
                Base64-encoded attachment content or error message
            """
            client = self.get_client()
            try:
                attachment_data = client.download_attachment(ticket_id, article_id, attachment_id)
                # Convert bytes to base64 string for transmission
                return base64.b64encode(attachment_data).decode("utf-8")
            except Exception as e:
                return f"Error downloading attachment: {e!s}"

        @self.mcp.tool()
        def add_ticket_tag(ticket_id: int, tag: str) -> dict[str, Any]:
            """Add a tag to a ticket.

            Args:
                ticket_id: The ticket ID
                tag: The tag to add

            Returns:
                Operation result
            """
            client = self.get_client()
            return client.add_ticket_tag(ticket_id, tag)

        @self.mcp.tool()
        def remove_ticket_tag(ticket_id: int, tag: str) -> dict[str, Any]:
            """Remove a tag from a ticket.

            Args:
                ticket_id: The ticket ID
                tag: The tag to remove

            Returns:
                Operation result
            """
            client = self.get_client()
            return client.remove_ticket_tag(ticket_id, tag)

    def _setup_user_org_tools(self) -> None:
        """Register user and organization tools."""

        @self.mcp.tool()
        def get_user(user_id: int) -> User:
            """Get user information by ID.

            Args:
                user_id: The user ID

            Returns:
                User details
            """
            client = self.get_client()
            user_data = client.get_user(user_id)
            return User(**user_data)

        @self.mcp.tool()
        def search_users(query: str, page: int = 1, per_page: int = 25) -> list[User]:
            """Search for users.

            Args:
                query: Search query (name, email, etc.)
                page: Page number
                per_page: Results per page

            Returns:
                List of users matching the query
            """
            client = self.get_client()
            users_data = client.search_users(query, page, per_page)
            return [User(**user) for user in users_data]

        @self.mcp.tool()
        def get_organization(org_id: int) -> Organization:
            """Get organization information by ID.

            Args:
                org_id: The organization ID

            Returns:
                Organization details
            """
            client = self.get_client()
            org_data = client.get_organization(org_id)
            return Organization(**org_data)

        @self.mcp.tool()
        def search_organizations(query: str, page: int = 1, per_page: int = 25) -> list[Organization]:
            """Search for organizations.

            Args:
                query: Search query (name, domain, etc.)
                page: Page number
                per_page: Results per page

            Returns:
                List of organizations matching the query
            """
            client = self.get_client()
            orgs_data = client.search_organizations(query, page, per_page)
            return [Organization(**org) for org in orgs_data]

        @self.mcp.tool()
        def get_current_user() -> User:
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

    def _setup_system_tools(self) -> None:
        """Register system information tools."""

        @self.mcp.tool()
        def get_ticket_stats(
            group: str | None = None,
            start_date: str | None = None,
            end_date: str | None = None,
        ) -> TicketStats:
            """Get ticket statistics using pagination for better performance.

            Args:
                group: Filter by group name
                start_date: Start date (ISO format) - NOT YET IMPLEMENTED
                end_date: End date (ISO format) - NOT YET IMPLEMENTED

            Returns:
                Ticket statistics

            Note: This implementation uses pagination to avoid loading all tickets
            into memory at once, improving performance for large datasets.
            """
            client = self.get_client()
            # TODO: Implement date filtering when the API supports it
            if start_date or end_date:
                logger.warning("Date filtering not yet implemented - ignoring date parameters")

            # Initialize counters
            total_count = 0
            open_count = 0
            closed_count = 0
            pending_count = 0
            escalated_count = 0

            # Process tickets in batches
            page = 1
            per_page = 100

            while True:
                # Get a batch of tickets
                tickets = client.search_tickets(group=group, page=page, per_page=per_page)

                if not tickets:
                    # No more tickets
                    break

                # Process this batch
                for ticket in tickets:
                    total_count += 1

                    # Handle both expanded (string) and non-expanded (object) state formats
                    state = ticket.get("state")
                    state_name = ""
                    if isinstance(state, str):
                        state_name = state
                    elif isinstance(state, dict):
                        state_name = str(state.get("name", ""))

                    # Count by state
                    if state_name in ["new", "open"]:
                        open_count += 1
                    elif state_name == "closed":
                        closed_count += 1
                    elif "pending" in state_name:
                        pending_count += 1

                    # Check for escalation
                    if (
                        ticket.get("first_response_escalation_at")
                        or ticket.get("close_escalation_at")
                        or ticket.get("update_escalation_at")
                    ):
                        escalated_count += 1

                # Move to next page
                page += 1

                # Safety check to prevent infinite loops
                if page > MAX_TICKETS_FOR_MEMORY_SCAN:  # Safety limit to prevent infinite loops
                    logger.warning("Reached maximum page limit, some tickets may not be counted")
                    break

            return TicketStats(
                total_count=total_count,
                open_count=open_count,
                closed_count=closed_count,
                pending_count=pending_count,
                escalated_count=escalated_count,
                avg_first_response_time=None,  # TODO: Calculate from ticket data
                avg_resolution_time=None,  # TODO: Calculate from ticket data
            )

        @self.mcp.tool()
        def list_groups() -> list[Group]:
            """Get all available groups (cached).

            Returns:
                List of all groups
            """
            return self._get_cached_groups()

        @self.mcp.tool()
        def list_ticket_states() -> list[TicketState]:
            """Get all available ticket states (cached).

            Returns:
                List of all ticket states
            """
            return self._get_cached_states()

        @self.mcp.tool()
        def list_ticket_priorities() -> list[TicketPriority]:
            """Get all available ticket priorities (cached).

            Returns:
                List of all ticket priorities
            """
            return self._get_cached_priorities()

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
                ticket = client.get_ticket(int(ticket_id), include_articles=True, article_limit=20)

                # Format ticket data as readable text
                lines = [
                    f"Ticket #{ticket['number']} - {ticket['title']}",
                    f"State: {ticket.get('state', {}).get('name', 'Unknown')}",
                    f"Priority: {ticket.get('priority', {}).get('name', 'Unknown')}",
                    f"Customer: {ticket.get('customer', {}).get('email', 'Unknown')}",
                    f"Created: {ticket.get('created_at', 'Unknown')}",
                    "",
                    "Articles:",
                    "",
                ]

                for article in ticket.get("articles", []):
                    lines.extend(
                        [
                            f"--- {article.get('created_at', 'Unknown')} by {(article.get('created_by') or {}).get('email', 'Unknown')} ---",
                            article.get("body", ""),
                            "",
                        ]
                    )

                return "\n".join(lines)
            except Exception as e:
                return f"Error retrieving ticket {ticket_id}: {e!s}"

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
            except Exception as e:
                return f"Error retrieving user {user_id}: {e!s}"

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
            except Exception as e:
                return f"Error retrieving organization {org_id}: {e!s}"

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
                    state = ticket.get("state")
                    state_name = ""
                    if isinstance(state, str):
                        state_name = state
                    elif isinstance(state, dict):
                        state_name = str(state.get("name", ""))

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

                        lines.append(f"  #{ticket.get('number', 'N/A')} - {ticket.get('title', 'No title')[:50]}...")
                        lines.append(f"    Priority: {priority_name}, Customer: {customer_email}")
                        lines.append(f"    Created: {ticket.get('created_at', 'Unknown')}")

                    if len(state_tickets) > MAX_TICKETS_PER_STATE_IN_QUEUE:
                        lines.append(f"    ... and {len(state_tickets) - MAX_TICKETS_PER_STATE_IN_QUEUE} more tickets")
                    lines.append("")

                return "\n".join(lines)
            except Exception as e:
                return f"Error retrieving queue for group {group}: {e!s}"

    def _setup_prompts(self) -> None:
        """Register all prompts with the MCP server."""

        @self.mcp.prompt()
        def analyze_ticket(ticket_id: int) -> str:
            """Generate a prompt to analyze a ticket."""
            return f"""Please analyze ticket {ticket_id} from Zammad. Use the get_ticket tool to retrieve the ticket details including all articles.

After retrieving the ticket, provide:
1. A summary of the issue
2. Current status and priority
3. Timeline of interactions
4. Suggested next steps or resolution

Use appropriate tools to gather any additional context about the customer or organization if needed."""

        @self.mcp.prompt()
        def draft_response(ticket_id: int, tone: str = "professional") -> str:
            """Generate a prompt to draft a response to a ticket."""
            return f"""Please help draft a {tone} response to ticket {ticket_id}. 

First, use get_ticket to understand the issue and conversation history. Then draft an appropriate response that:
1. Acknowledges the customer's concern
2. Provides a clear solution or next steps
3. Maintains a {tone} tone throughout
4. Is concise and easy to understand

After drafting, you can use add_article to add the response to the ticket if approved."""

        @self.mcp.prompt()
        def escalation_summary(group: str | None = None) -> str:
            """Generate a prompt to summarize escalated tickets."""
            group_filter = f" for group '{group}'" if group else ""
            return f"""Please provide a summary of escalated tickets{group_filter}.

Use search_tickets to find tickets with escalation times set. For each escalated ticket:
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

# Legacy constants and functions for backward compatibility with tests
_UNINITIALIZED = None
zammad_client = None


async def initialize() -> None:
    """Initialize the Zammad client (legacy wrapper for test compatibility)."""
    await server.initialize()
    # Update the module-level client reference
    globals()["zammad_client"] = server.client


def search_tickets(
    query: str | None = None,
    state: str | None = None,
    priority: str | None = None,
    group: str | None = None,
    owner: str | None = None,
    customer: str | None = None,
    page: int = 1,
    per_page: int = 25,
) -> list[Ticket]:
    """Search for tickets (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    tickets_data = zammad_client.search_tickets(
        query=query,
        state=state,
        priority=priority,
        group=group,
        owner=owner,
        customer=customer,
        page=page,
        per_page=per_page,
    )
    return [Ticket(**ticket) for ticket in tickets_data]


def get_ticket(
    ticket_id: int,
    include_articles: bool = False,
    article_limit: int = 10,
    article_offset: int = 0,
) -> Ticket:
    """Get a ticket by ID (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    ticket_data = zammad_client.get_ticket(ticket_id, include_articles, article_limit, article_offset)
    return Ticket(**ticket_data)


def create_ticket(
    title: str,
    group: str,
    customer: str,
    article_body: str,
    state: str = "new",
    priority: str = "2 normal",
    article_type: str = "note",
    article_internal: bool = False,
) -> Ticket:
    """Create a new ticket (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    ticket_data = zammad_client.create_ticket(
        title=title,
        group=group,
        customer=customer,
        article_body=article_body,
        state=state,
        priority=priority,
        article_type=article_type,
        article_internal=article_internal,
    )
    return Ticket(**ticket_data)


def add_article(
    ticket_id: int,
    body: str,
    article_type: str = "note",
    internal: bool = False,
    sender: str = "Agent",
) -> Article:
    """Add an article to a ticket (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    article_data = zammad_client.add_article(
        ticket_id=ticket_id,
        body=body,
        article_type=article_type,
        internal=internal,
        sender=sender,
    )
    return Article(**article_data)


def get_article_attachments(ticket_id: int, article_id: int) -> list[Attachment]:
    """Get list of attachments for a ticket article (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    attachments_data = zammad_client.get_article_attachments(ticket_id, article_id)
    return [Attachment(**attachment) for attachment in attachments_data]


def download_attachment(ticket_id: int, article_id: int, attachment_id: int) -> str:
    """Download an attachment from a ticket article (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    try:
        attachment_data = zammad_client.download_attachment(ticket_id, article_id, attachment_id)
        # Convert bytes to base64 string for transmission
        return base64.b64encode(attachment_data).decode("utf-8")
    except Exception as e:
        return f"Error downloading attachment: {e!s}"


def get_user(user_id: int) -> User:
    """Get a user by ID (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    user_data = zammad_client.get_user(user_id)
    return User(**user_data)


def add_ticket_tag(ticket_id: int, tag: str) -> dict[str, Any]:
    """Add a tag to a ticket (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    return zammad_client.add_ticket_tag(ticket_id, tag)


def remove_ticket_tag(ticket_id: int, tag: str) -> dict[str, Any]:
    """Remove a tag from a ticket (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    return zammad_client.remove_ticket_tag(ticket_id, tag)


def update_ticket(
    ticket_id: int,
    title: str | None = None,
    state: str | None = None,
    priority: str | None = None,
    owner: str | None = None,
    group: str | None = None,
) -> Ticket:
    """Update a ticket (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    ticket_data = zammad_client.update_ticket(
        ticket_id,
        title=title,
        state=state,
        priority=priority,
        owner=owner,
        group=group,
    )
    return Ticket(**ticket_data)


def get_organization(org_id: int) -> Organization:
    """Get organization by ID (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    org_data = zammad_client.get_organization(org_id)
    return Organization(**org_data)


def search_organizations(
    query: str,
    page: int = 1,
    per_page: int = 25,
) -> list[Organization]:
    """Search organizations (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    results = zammad_client.search_organizations(query=query, page=page, per_page=per_page)
    return [Organization(**org) for org in results]


def list_groups() -> list[Group]:
    """List all groups (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    groups = zammad_client.get_groups()
    return [Group(**g) for g in groups]


def list_ticket_states() -> list[TicketState]:
    """List all ticket states (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    states = zammad_client.get_ticket_states()
    return [TicketState(**s) for s in states]


def list_ticket_priorities() -> list[TicketPriority]:
    """List all ticket priorities (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    priorities = zammad_client.get_ticket_priorities()
    return [TicketPriority(**p) for p in priorities]


def get_current_user() -> User:
    """Get current user (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    user_data = zammad_client.get_current_user()
    return User(**user_data)


def search_users(
    query: str,
    page: int = 1,
    per_page: int = 25,
) -> list[User]:
    """Search users (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")
    results = zammad_client.search_users(query=query, page=page, per_page=per_page)
    return [User(**user) for user in results]


def get_ticket_stats(
    group: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> TicketStats:
    """Get ticket statistics (legacy wrapper for test compatibility)."""
    if zammad_client is None:
        raise RuntimeError("Zammad client not initialized")

    # This implementation matches the tool implementation
    if start_date or end_date:
        logger.warning("Date filtering not yet implemented - ignoring date parameters")

    all_tickets = zammad_client.search_tickets(group=group, per_page=100)

    def get_state_name(ticket: dict[str, Any]) -> str:
        state = ticket.get("state")
        if isinstance(state, str):
            return state
        if isinstance(state, dict):
            name = state.get("name", "")
            return str(name) if name else ""
        return ""

    open_count = sum(1 for t in all_tickets if get_state_name(t) in ["new", "open"])
    closed_count = sum(1 for t in all_tickets if get_state_name(t) == "closed")
    pending_count = sum(1 for t in all_tickets if "pending" in get_state_name(t))
    escalated_count = sum(
        1
        for t in all_tickets
        if (t.get("first_response_escalation_at") or t.get("close_escalation_at") or t.get("update_escalation_at"))
    )

    return TicketStats(
        total_count=len(all_tickets),
        open_count=open_count,
        closed_count=closed_count,
        pending_count=pending_count,
        escalated_count=escalated_count,
    )


def main() -> None:
    """Main entry point for the server."""
    mcp.run()
