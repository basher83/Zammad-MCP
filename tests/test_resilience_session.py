"""Tests for rate limiting and retry behavior of the resilient session."""

import pytest
import requests

from mcp_zammad.resilience import RetryExhaustedError
from tests.resilience_support import URL, FakeClock, Harness, make_response


def test_safe_request_retries_until_success() -> None:
    ok = make_response(200)
    harness = Harness([make_response(429), make_response(503), ok])

    assert harness.session.get(URL) is ok
    assert harness.calls == [("GET", URL)] * 3
    assert harness.sleeps == [1.0, 2.0]


def test_backoff_base_scales_delays() -> None:
    harness = Harness([make_response(502), make_response(502), make_response(200)], retry_backoff_base=0.5)

    harness.session.get(URL)

    assert harness.sleeps == [0.5, 1.0]


def test_retry_after_header_overrides_backoff() -> None:
    harness = Harness([make_response(429, {"Retry-After": "7"}), make_response(200)])

    harness.session.get(URL)

    assert harness.sleeps == [7.0]


def test_malformed_retry_after_falls_back_to_backoff() -> None:
    harness = Harness([make_response(429, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), make_response(200)])

    harness.session.get(URL)

    assert harness.sleeps == [1.0]


def test_retry_after_is_bounded() -> None:
    harness = Harness([make_response(429, {"Retry-After": "999"}), make_response(200)])

    harness.session.get(URL)

    assert harness.sleeps == [60.0]


def test_retry_cap_raises_retry_exhausted() -> None:
    harness = Harness([make_response(429)] * 3, max_retries=2)

    with pytest.raises(RetryExhaustedError, match="3 attempts") as exc_info:
        harness.session.get(URL)

    assert "429" in str(exc_info.value)
    assert isinstance(exc_info.value, requests.exceptions.RequestException)
    assert len(harness.calls) == 3


def test_non_retryable_client_error_is_returned_once() -> None:
    not_found = make_response(404)
    harness = Harness([not_found])

    assert harness.session.get(URL) is not_found
    assert len(harness.calls) == 1
    assert harness.sleeps == []


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_write_methods_are_never_retried(method: str) -> None:
    unavailable = make_response(503)
    harness = Harness([unavailable])

    assert harness.session.request(method, URL, json={}) is unavailable
    assert harness.calls == [(method, URL)]
    assert harness.sleeps == []


def test_connection_errors_retry_then_reraise() -> None:
    harness = Harness(
        [requests.exceptions.ConnectionError("boom"), requests.exceptions.Timeout("slow")],
        max_retries=1,
    )

    with pytest.raises(requests.exceptions.Timeout):
        harness.session.get(URL)

    assert len(harness.calls) == 2
    assert harness.sleeps == [1.0]


def test_rate_limit_disabled_by_default_never_sleeps() -> None:
    harness = Harness([make_response(200)] * 5)

    for _ in range(5):
        harness.session.get(URL)

    assert harness.sleeps == []


def test_rate_limit_waits_for_next_window() -> None:
    clock = FakeClock(start=1000.0)
    harness = Harness(
        [make_response(200)] * 4,
        clock=clock,
        rate_limit_enabled=True,
        rate_limit_requests=2,
        rate_limit_window=10.0,
    )

    harness.session.get(URL)
    clock.advance(3.0)
    harness.session.get(URL)
    clock.advance(2.0)
    harness.session.get(URL)
    harness.session.get(URL)

    assert harness.sleeps == [5.0]
    assert len(harness.calls) == 4


def test_rate_limit_counts_every_attempt() -> None:
    harness = Harness(
        [make_response(503), make_response(200)],
        rate_limit_enabled=True,
        rate_limit_requests=1,
        rate_limit_window=10.0,
    )

    harness.session.get(URL)

    # Retry backoff (1s) then wait for the rest of the window (9s) before the second attempt.
    assert harness.sleeps == [1.0, 9.0]


def test_verb_helpers_delegate_to_request() -> None:
    harness = Harness([make_response(200)] * 3)

    harness.session.post(URL, json={"title": "x"})
    harness.session.put(URL)
    harness.session.delete(URL)

    assert [method for method, _ in harness.calls] == ["POST", "PUT", "DELETE"]


def test_session_state_is_delegated_to_wrapped_session() -> None:
    harness = Harness([])

    harness.session.headers["X-On-Behalf-Of"] = "agent"
    harness.session.close()

    assert harness.inner.headers["X-On-Behalf-Of"] == "agent"
    assert harness.session.verify is True
    assert harness.inner.closed is True
