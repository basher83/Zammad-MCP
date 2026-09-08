"""Tests for MCP-visible guidance when resilience limits are hit."""

import requests

from mcp_zammad.resilience import CircuitOpenError, RetryExhaustedError
from mcp_zammad.server import _handle_api_error


def test_retry_exhausted_error_gives_rate_limit_guidance() -> None:
    error = RetryExhaustedError("GET https://z/api/v1/tickets failed after 4 attempts; last status 429")

    message = _handle_api_error(error, context="searching tickets")

    assert message.startswith("Error: Zammad rate limit reached during searching tickets")
    assert "4 attempts" in message
    assert "ZAMMAD_RATE_LIMIT_ENABLED" in message


def test_circuit_open_error_gives_recovery_guidance() -> None:
    error = CircuitOpenError("Zammad circuit breaker is open; retry in 20.0s")

    message = _handle_api_error(error, context="retrieving ticket 7")

    assert message.startswith("Error: Zammad is temporarily unavailable during retrieving ticket 7")
    assert "20.0s" in message


def test_existing_error_branches_are_unchanged() -> None:
    assert _handle_api_error(requests.exceptions.HTTPError("404 not found"), "x").startswith(
        "Error: Resource not found"
    )
    assert _handle_api_error(requests.exceptions.Timeout("timeout"), "x").startswith("Error: Request timeout")
