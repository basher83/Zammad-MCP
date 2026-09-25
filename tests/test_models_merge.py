"""Tests for ticket merge request and result models."""

import pytest
from pydantic import ValidationError

from mcp_zammad.models import Ticket, TicketMergeParams, TicketMergeResult

TARGET_TICKET = {
    "id": 20,
    "number": "20002",
    "title": "Incident: cron failures",
    "group_id": 1,
    "state_id": 2,
    "priority_id": 2,
    "customer_id": 3,
    "created_by_id": 1,
    "updated_by_id": 1,
    "created_at": "2026-09-01T00:00:00Z",
    "updated_at": "2026-09-01T00:00:00Z",
}


class TestTicketMergeParams:
    """Validation of merge request parameters."""

    def test_accepts_target_ticket_number(self):
        params = TicketMergeParams(source_ticket_id=10, target_ticket_number="20002")
        assert params.source_ticket_id == 10
        assert params.target_ticket_number == "20002"
        assert params.target_ticket_id is None

    def test_accepts_target_ticket_id(self):
        params = TicketMergeParams(source_ticket_id=10, target_ticket_id=20)
        assert params.target_ticket_id == 20
        assert params.target_ticket_number is None

    def test_rejects_non_positive_source_id(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            TicketMergeParams(source_ticket_id=0, target_ticket_number="20002")

    def test_rejects_non_positive_target_id(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            TicketMergeParams(source_ticket_id=10, target_ticket_id=-1)

    def test_rejects_empty_target_number(self):
        with pytest.raises(ValidationError, match="at least 1 character"):
            TicketMergeParams(source_ticket_id=10, target_ticket_number="   ")

    def test_rejects_missing_target(self):
        with pytest.raises(ValidationError, match="exactly one of"):
            TicketMergeParams(source_ticket_id=10)

    def test_rejects_both_target_forms(self):
        with pytest.raises(ValidationError, match="exactly one of"):
            TicketMergeParams(source_ticket_id=10, target_ticket_number="20002", target_ticket_id=20)

    def test_rejects_unknown_fields(self):
        with pytest.raises(ValidationError):
            TicketMergeParams(source_ticket_id=10, target_ticket_number="20002", target_ticket="20002")


class TestTicketMergeResult:
    """Shape of the merge result returned to MCP clients."""

    def test_wraps_result_and_target_ticket(self):
        result = TicketMergeResult(result="success", target_ticket=Ticket(**TARGET_TICKET))
        assert result.result == "success"
        assert result.target_ticket.number == "20002"

    def test_requires_target_ticket(self):
        with pytest.raises(ValidationError):
            TicketMergeResult(result="success")
