"""Zammad webhook delivery boundary: signature validation and payload normalization."""

import hashlib
import hmac
import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from .events import EventType, WebhookEvent

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "x-hub-signature"
TRIGGER_HEADER = "x-zammad-trigger"
SIGNATURE_PREFIX = "sha1="


class EventSink(Protocol):
    """Destination for accepted, normalized events."""

    def append(self, event: WebhookEvent) -> None: ...  # codacy: ignore E704


class WebhookRejectedError(Exception):
    """Delivery rejected; carries the HTTP status and safe client-facing reason."""

    def __init__(self, status_code: int, error: str) -> None:
        """Record the rejection status and a message that never echoes payload content."""
        self.status_code = status_code
        self.error = error
        super().__init__(error)


@dataclass(frozen=True)
class DeliveryResult:
    """Transport-agnostic outcome of a webhook delivery."""

    status_code: int
    body: dict[str, Any]


def verify_signature(body: bytes, header: str | None, secret: str) -> None:
    """Validate Zammad's ``X-Hub-Signature`` (``sha1=<hex>``) against ``body`` in constant time.

    Raises:
        WebhookRejectedError: 401 when the header is missing, malformed, or does not match.
    """
    if not header or not header.startswith(SIGNATURE_PREFIX):
        raise WebhookRejectedError(401, "Missing or malformed X-Hub-Signature header; expected 'sha1=<hex digest>'")
    expected = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    if not hmac.compare_digest(expected, header[len(SIGNATURE_PREFIX) :].lower()):
        raise WebhookRejectedError(401, "X-Hub-Signature does not match the configured webhook secret")


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _classify(ticket: Mapping[str, Any], article: Mapping[str, Any] | None) -> EventType:
    if article is None:
        return "ticket.update"
    if ticket.get("article_count") == 1:
        return "ticket.create"
    return "ticket.article.create"


def normalize_payload(payload: Any, *, trigger: str | None, received_at: datetime) -> WebhookEvent:
    """Reduce a Zammad ticket webhook payload to its stable identifying fields.

    Raises:
        WebhookRejectedError: 400 when the payload is not a ticket delivery with integer identifiers.
    """
    ticket = payload.get("ticket") if isinstance(payload, Mapping) else None
    ticket_id = _optional_int(ticket.get("id")) if isinstance(ticket, Mapping) else None
    if ticket is None or ticket_id is None:
        raise WebhookRejectedError(
            400, "Unsupported payload: expected a Zammad ticket webhook with an integer ticket.id"
        )
    article = payload.get("article")
    article_id = _optional_int(article.get("id")) if isinstance(article, Mapping) else None
    if article is not None and article_id is None:
        raise WebhookRejectedError(400, "Unsupported payload: ticket article must carry an integer article.id")
    number = ticket.get("number")
    return WebhookEvent(
        event_type=_classify(ticket, article),
        ticket_id=ticket_id,
        ticket_number=str(number) if number is not None else None,
        article_id=article_id,
        trigger=trigger,
        source_timestamp=_optional_timestamp(ticket.get("updated_at")),
        received_at=received_at,
    )


class WebhookHandler:
    """Validate a raw Zammad delivery and hand the normalized event to the sink."""

    def __init__(
        self,
        *,
        secret_provider: Callable[[], str | None],
        clock: Callable[[], datetime],
        sink: EventSink,
    ) -> None:
        """Wire the injected secret lookup, receipt clock, and event sink."""
        self._secret_provider = secret_provider
        self._clock = clock
        self._sink = sink

    def handle_delivery(self, body: bytes, headers: Mapping[str, str]) -> DeliveryResult:
        """Process one delivery and return the HTTP status/body to send back to Zammad."""
        try:
            event = self._accept(body, headers)
        except WebhookRejectedError as rejected:
            logger.warning("Rejected Zammad webhook delivery (%s): %s", rejected.status_code, rejected.error)
            return DeliveryResult(rejected.status_code, {"status": "rejected", "error": rejected.error})
        self._sink.append(event)
        logger.info("Accepted Zammad webhook %s for ticket %s", event.event_type, event.ticket_id)
        return DeliveryResult(202, {"status": "accepted", "event_type": event.event_type, "ticket_id": event.ticket_id})

    def _accept(self, body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
        secret = self._secret_provider()
        if not secret:
            raise WebhookRejectedError(503, "Webhook ingestion is disabled: ZAMMAD_WEBHOOK_SECRET is not configured")
        verify_signature(body, headers.get(SIGNATURE_HEADER), secret)
        try:
            payload = json.loads(body)
        except ValueError:
            raise WebhookRejectedError(400, "Request body is not valid JSON") from None
        return normalize_payload(payload, trigger=headers.get(TRIGGER_HEADER), received_at=self._clock())
