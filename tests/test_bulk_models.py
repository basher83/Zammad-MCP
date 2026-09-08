"""Tests for bulk ticket update request and result models."""

import pytest
from pydantic import ValidationError

from mcp_zammad.models import BulkTicketUpdateParams, BulkUpdateFailure, BulkUpdateResult


def test_accepts_full_request():
    """A request with IDs and every supported action validates."""
    params = BulkTicketUpdateParams(
        ticket_ids=[1, 2, 3],
        title="Escalated",
        state="closed",
        priority="3 high",
        owner="agent@example.com",
        group="Support",
        time_unit=1.5,
        add_tags=["vip"],
        remove_tags=["pending-review"],
        note="Closed in bulk",
        delay_seconds=0.5,
    )
    assert params.ticket_ids == [1, 2, 3]
    assert params.add_tags == ["vip"]
    assert params.delay_seconds == 0.5


def test_defaults_to_no_delay():
    """Delay is off unless requested."""
    params = BulkTicketUpdateParams(ticket_ids=[1], state="closed")
    assert params.delay_seconds == 0


def test_rejects_empty_ticket_ids():
    """At least one ticket ID is required."""
    with pytest.raises(ValidationError, match="ticket_ids"):
        BulkTicketUpdateParams(ticket_ids=[], state="closed")


def test_rejects_more_than_100_ticket_ids():
    """The batch size is capped at 100."""
    with pytest.raises(ValidationError, match="ticket_ids"):
        BulkTicketUpdateParams(ticket_ids=list(range(1, 102)), state="closed")


def test_rejects_duplicate_ticket_ids():
    """Duplicate IDs would apply the same change twice."""
    with pytest.raises(ValidationError, match="unique"):
        BulkTicketUpdateParams(ticket_ids=[1, 1], state="closed")


def test_rejects_non_positive_ticket_id():
    """Ticket IDs must be positive database IDs."""
    with pytest.raises(ValidationError, match="greater than 0"):
        BulkTicketUpdateParams(ticket_ids=[0], state="closed")


def test_rejects_request_without_any_operation():
    """A request that changes nothing is a caller mistake."""
    with pytest.raises(ValidationError, match="at least one"):
        BulkTicketUpdateParams(ticket_ids=[1])


def test_rejects_empty_tag_list_as_operation():
    """Empty tag lists do not count as an operation."""
    with pytest.raises(ValidationError, match="at least one"):
        BulkTicketUpdateParams(ticket_ids=[1], add_tags=[])


@pytest.mark.parametrize("field", ["add_tags", "remove_tags"])
@pytest.mark.parametrize("tag", ["", "x" * 101])
def test_rejects_invalid_tag_names(field, tag):
    """Tag names follow the same bounds as the single-tag tools."""
    with pytest.raises(ValidationError, match=r"at (least|most)"):
        BulkTicketUpdateParams(ticket_ids=[1], **{field: [tag]})


def test_escapes_html_in_title_and_note():
    """Title and note follow the single-ticket sanitization rules."""
    params = BulkTicketUpdateParams(ticket_ids=[1], title="<b>x</b>", note="<script>y</script>")
    assert params.title == "&lt;b&gt;x&lt;/b&gt;"
    assert params.note == "&lt;script&gt;y&lt;/script&gt;"


@pytest.mark.parametrize("time_unit", [0, -1])
def test_rejects_non_positive_time_unit(time_unit):
    """Time accounting must be a positive amount."""
    with pytest.raises(ValidationError, match="time_unit"):
        BulkTicketUpdateParams(ticket_ids=[1], time_unit=time_unit)


def test_rejects_negative_delay():
    """A negative delay is meaningless."""
    with pytest.raises(ValidationError, match="delay_seconds"):
        BulkTicketUpdateParams(ticket_ids=[1], state="closed", delay_seconds=-1)


def test_result_exposes_success_and_failure_details():
    """The result reports exactly which tickets changed and why others failed."""
    result = BulkUpdateResult(
        successful_ticket_ids=[1, 3],
        failed=[BulkUpdateFailure(ticket_id=2, error="Error: Resource not found")],
        total_processed=3,
        total_successful=2,
    )
    assert result.successful_ticket_ids == [1, 3]
    assert result.failed[0].ticket_id == 2
    assert result.total_processed == 3
    assert result.total_successful == 2
