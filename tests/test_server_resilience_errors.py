"""Tests for MCP-visible guidance when resilience limits are hit."""

import pytest
import requests

from mcp_zammad.resilience import CircuitOpenError, RetryExhaustedError
from mcp_zammad.server import _handle_api_error


def test_retry_exhausted_error_gives_rate_limit_guidance() -> None:
    error = RetryExhaustedError(
        "GET https://z/api/v1/tickets failed after 4 attempts; last status 429", status_code=429
    )

    message = _handle_api_error(error, context="searching tickets")

    assert message.startswith("Error: Zammad rate limit reached during searching tickets")
    assert "4 attempts" in message
    assert "ZAMMAD_RATE_LIMIT_ENABLED" in message


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_retry_exhausted_on_server_error_gives_outage_guidance(status: int) -> None:
    error = RetryExhaustedError(
        f"GET https://z/api/v1/tickets failed after 4 attempts; last status {status}", status_code=status
    )

    message = _handle_api_error(error, context="listing tickets")

    assert message.startswith("Error: Zammad server error during listing tickets")
    assert str(status) in message
    assert "rate limit" not in message.lower()
    assert "ZAMMAD_RATE_LIMIT_ENABLED" not in message


@pytest.mark.parametrize(
    "error",
    [
        requests.exceptions.HTTPError("429 Client Error: Too Many Requests for url: https://z/api/v1/tickets"),
        requests.exceptions.HTTPError('{"error": "Too many requests"}'),
    ],
)
def test_throttled_write_gives_rate_limit_guidance(error: Exception) -> None:
    message = _handle_api_error(error, context="creating ticket")

    assert message.startswith("Error: Zammad rate limit reached during creating ticket")
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
