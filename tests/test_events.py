"""Behavior tests for the bounded in-memory webhook event store."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from mcp_zammad.events import EventStore, ListEventsParams, WebhookEvent

BASE = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


def event(seq: int) -> WebhookEvent:
    return WebhookEvent(
        event_type="ticket.update", ticket_id=seq, received_at=BASE + timedelta(seconds=seq), trigger=None
    )


def test_store_evicts_oldest_when_capacity_exceeded() -> None:
    store = EventStore(capacity=2)
    for seq in (1, 2, 3):
        store.append(event(seq))

    assert [e.ticket_id for e in store.list()] == [2, 3]
    assert store.capacity == 2


def test_list_returns_events_in_receipt_order() -> None:
    store = EventStore(capacity=5)
    for seq in (3, 1, 2):
        store.append(event(seq))

    assert [e.ticket_id for e in store.list()] == [3, 1, 2]


def test_list_since_excludes_events_at_or_before_cursor() -> None:
    store = EventStore(capacity=5)
    for seq in (1, 2, 3):
        store.append(event(seq))

    result = store.list(since=BASE + timedelta(seconds=2))

    assert [e.ticket_id for e in result] == [3]


def test_list_limit_returns_most_recent_events() -> None:
    store = EventStore(capacity=5)
    for seq in (1, 2, 3):
        store.append(event(seq))

    assert [e.ticket_id for e in store.list(limit=2)] == [2, 3]


def test_list_since_accepts_naive_cursor_as_utc() -> None:
    store = EventStore(capacity=5)
    store.append(event(1))

    assert store.list(since=datetime(2026, 9, 8, 12, 0)) == store.list()  # noqa: DTZ001 - naive cursor is the case


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_list_params_reject_out_of_range_limit(limit: int) -> None:
    with pytest.raises(ValidationError):
        ListEventsParams(limit=limit)


def test_list_params_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ListEventsParams(sinc="2026-09-08T12:00:00Z")  # type: ignore[call-arg]
