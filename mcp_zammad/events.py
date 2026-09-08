"""Bounded in-memory retention of normalized Zammad webhook events."""

from collections import deque
from datetime import datetime, timezone
from typing import Literal

from pydantic import Field

from .models import StrictBaseModel

DEFAULT_EVENT_CAPACITY = 1000
MAX_LIST_LIMIT = 100

EventType = Literal["ticket.create", "ticket.update", "ticket.article.create"]


class WebhookEvent(StrictBaseModel):
    """Normalized, body-free record of one accepted Zammad webhook delivery."""

    event_type: EventType
    ticket_id: int
    ticket_number: str | None = None
    article_id: int | None = None
    trigger: str | None = None
    source_timestamp: datetime | None = None
    received_at: datetime


class ListEventsParams(StrictBaseModel):
    """Filter for the ``zammad_list_events`` tool."""

    since: datetime | None = Field(
        default=None,
        description="Return only events received strictly after this timestamp (ISO 8601, naive means UTC).",
    )
    limit: int = Field(
        default=50, ge=1, le=MAX_LIST_LIMIT, description=f"Maximum events to return (1-{MAX_LIST_LIMIT})."
    )


class ListEventsResult(StrictBaseModel):
    """Tool output: retained events plus retention metadata for polling clients."""

    events: list[WebhookEvent]
    count: int
    capacity: int
    retained_total: int
    next_since: datetime | None


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class EventStore:
    """Process-local FIFO store; oldest events are evicted once ``capacity`` is reached."""

    def __init__(self, capacity: int = DEFAULT_EVENT_CAPACITY) -> None:
        """Create an empty store that retains at most ``capacity`` events."""
        self._events: deque[WebhookEvent] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        """Maximum number of events retained before FIFO eviction."""
        return self._events.maxlen or 0

    def __len__(self) -> int:
        """Number of currently retained events."""
        return len(self._events)

    def append(self, event: WebhookEvent) -> None:
        """Retain ``event``, evicting the oldest event when at capacity."""
        self._events.append(event)

    def list(self, *, since: datetime | None = None, limit: int | None = None) -> list[WebhookEvent]:
        """Return the oldest ``limit`` retained events received after ``since``, in receipt order.

        Taking the oldest page (not the newest) lets a client pass the last ``received_at``
        back as ``since`` and walk a backlog larger than ``limit`` without skipping events.
        """
        events = list(self._events)
        if since is not None:
            cutoff = _as_utc(since)
            events = [e for e in events if _as_utc(e.received_at) > cutoff]
        if limit is not None:
            events = events[:limit]
        return events
