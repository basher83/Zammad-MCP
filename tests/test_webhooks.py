"""Contract tests for the Zammad webhook delivery boundary."""

import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest

from mcp_zammad.events import EventStore
from mcp_zammad.webhooks import WebhookHandler

SIGNING_KEY = "unit-test-hmac-key"  # not a real credential
RECEIVED_AT = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


def sign(body: bytes, secret: str = SIGNING_KEY) -> str:
    return "sha1=" + hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()


def ticket_payload(*, article: dict | None = None, article_count: int = 3) -> bytes:
    ticket = {
        "id": 81,
        "number": "10081",
        "title": "Webhook-Test",
        "state": "open",
        "article_count": article_count,
        "updated_at": "2026-09-08T11:59:00.000Z",
    }
    return json.dumps({"ticket": ticket, "article": article}).encode()


def article() -> dict:
    return {"id": 104, "ticket_id": 81, "body": "<p>secret body</p>", "created_at": "2026-09-08T11:59:00.000Z"}


def headers(signature: str | None, **extra: str) -> dict[str, str]:
    result = {"content-type": "application/json", **extra}
    if signature is not None:
        result["x-hub-signature"] = signature
    return result


@pytest.fixture
def store() -> EventStore:
    return EventStore(capacity=10)


@pytest.fixture
def handler(store: EventStore) -> WebhookHandler:
    return WebhookHandler(secret_provider=lambda: SIGNING_KEY, clock=lambda: RECEIVED_AT, sink=store)


def test_signed_ticket_update_is_accepted_and_normalized(handler: WebhookHandler, store: EventStore) -> None:
    body = ticket_payload()

    result = handler.handle_delivery(body, headers(sign(body), **{"x-zammad-trigger": "notify-mcp"}))

    assert result.status_code == 202
    assert result.body == {"status": "accepted", "event_type": "ticket.update", "ticket_id": 81}
    [event] = store.list()
    assert event.event_type == "ticket.update"
    assert event.ticket_id == 81
    assert event.ticket_number == "10081"
    assert event.article_id is None
    assert event.trigger == "notify-mcp"
    assert event.received_at == RECEIVED_AT
    assert event.source_timestamp == datetime(2026, 9, 8, 11, 59, tzinfo=timezone.utc)


def test_article_delivery_is_classified_without_retaining_body(handler: WebhookHandler, store: EventStore) -> None:
    body = ticket_payload(article=article())

    result = handler.handle_delivery(body, headers(sign(body)))

    assert result.status_code == 202
    [event] = store.list()
    assert event.event_type == "ticket.article.create"
    assert event.article_id == 104
    assert "secret body" not in event.model_dump_json()


def test_first_article_is_classified_as_ticket_create(handler: WebhookHandler, store: EventStore) -> None:
    body = ticket_payload(article=article(), article_count=1)

    handler.handle_delivery(body, headers(sign(body)))

    assert store.list()[0].event_type == "ticket.create"


def test_missing_secret_returns_503_and_stores_nothing(store: EventStore) -> None:
    handler = WebhookHandler(secret_provider=lambda: None, clock=lambda: RECEIVED_AT, sink=store)
    body = ticket_payload()

    result = handler.handle_delivery(body, headers(sign(body)))

    assert result.status_code == 503
    assert "ZAMMAD_WEBHOOK_SECRET" in result.body["error"]
    assert store.list() == []


@pytest.mark.parametrize(
    "signature",
    [None, "", "sha256=abc", "sha1=nothex", sign(b"other body"), sign(ticket_payload(), "wrong-secret")],
)
def test_missing_or_invalid_signature_returns_401(handler: WebhookHandler, store: EventStore, signature) -> None:
    result = handler.handle_delivery(ticket_payload(), headers(signature))

    assert result.status_code == 401
    assert store.list() == []


def test_malformed_json_returns_400(handler: WebhookHandler, store: EventStore) -> None:
    body = b"{not json"

    result = handler.handle_delivery(body, headers(sign(body)))

    assert result.status_code == 400
    assert store.list() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"user": {"id": 1}},
        {"ticket": {"number": "10081"}},
        {"ticket": {"id": "eighty-one"}},
        {"ticket": {"id": 81}, "article": {"body": "no id"}},
        [1, 2, 3],
    ],
)
def test_unsupported_payload_shape_returns_400(handler: WebhookHandler, store: EventStore, payload) -> None:
    body = json.dumps(payload).encode()

    result = handler.handle_delivery(body, headers(sign(body)))

    assert result.status_code == 400
    assert "ticket" in result.body["error"]
    assert store.list() == []


@pytest.mark.parametrize("updated_at", [None, "not-a-timestamp", 12345])
def test_missing_or_unparseable_source_timestamp_is_tolerated(
    handler: WebhookHandler, store: EventStore, updated_at
) -> None:
    body = json.dumps({"ticket": {"id": 5, "updated_at": updated_at}}).encode()

    result = handler.handle_delivery(body, headers(sign(body)))

    assert result.status_code == 202
    assert store.list()[0].source_timestamp is None
