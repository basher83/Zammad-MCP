"""Tests for circuit breaker state transitions at the resilient session boundary."""

import pytest
import requests

from mcp_zammad.resilience import CircuitOpenError, RetryExhaustedError
from tests.resilience_support import URL, FakeClock, Harness, make_response


def _tripped_harness(outcomes: list[object], clock: FakeClock) -> Harness:
    """Return a harness whose circuit has just opened after two failures."""
    harness = Harness(
        [make_response(503), make_response(503), *outcomes],
        clock=clock,
        max_retries=0,
        circuit_failure_threshold=2,
        circuit_recovery_timeout=30.0,
    )
    for _ in range(2):
        with pytest.raises(RetryExhaustedError):
            harness.session.get(URL)
    return harness


def test_circuit_opens_after_failure_threshold() -> None:
    harness = _tripped_harness([make_response(200)], FakeClock())

    with pytest.raises(CircuitOpenError, match="open") as exc_info:
        harness.session.get(URL)

    assert isinstance(exc_info.value, requests.exceptions.RequestException)
    assert len(harness.calls) == 2


def test_open_circuit_rejects_until_recovery_timeout() -> None:
    clock = FakeClock()
    harness = _tripped_harness([make_response(200)], clock)

    clock.advance(29.0)
    with pytest.raises(CircuitOpenError):
        harness.session.get(URL)

    clock.advance(1.0)
    assert harness.session.get(URL).status_code == 200
    assert len(harness.calls) == 3


def test_half_open_success_closes_circuit_and_resets_failures() -> None:
    clock = FakeClock()
    harness = _tripped_harness([make_response(200), make_response(503), make_response(200)], clock)

    clock.advance(30.0)
    harness.session.get(URL)
    with pytest.raises(RetryExhaustedError):
        harness.session.get(URL)

    # One failure after reset stays below the threshold of two, so the circuit remains closed.
    assert harness.session.get(URL).status_code == 200
    assert len(harness.calls) == 5


def test_half_open_failure_reopens_circuit() -> None:
    clock = FakeClock()
    harness = _tripped_harness([make_response(503), make_response(200)], clock)

    clock.advance(30.0)
    with pytest.raises(RetryExhaustedError):
        harness.session.get(URL)

    with pytest.raises(CircuitOpenError):
        harness.session.get(URL)
    assert len(harness.calls) == 3


def test_non_retryable_responses_do_not_count_as_failures() -> None:
    harness = Harness([make_response(404), make_response(404), make_response(200)], circuit_failure_threshold=1)

    harness.session.get(URL)
    harness.session.get(URL)

    assert harness.session.get(URL).status_code == 200
    assert len(harness.calls) == 3


def test_write_failures_count_toward_circuit() -> None:
    harness = Harness([make_response(503), make_response(200)], circuit_failure_threshold=1)

    harness.session.post(URL)

    with pytest.raises(CircuitOpenError):
        harness.session.get(URL)
    assert len(harness.calls) == 1


def test_circuit_open_error_reports_remaining_recovery_time() -> None:
    clock = FakeClock()
    harness = _tripped_harness([], clock)

    clock.advance(10.0)
    with pytest.raises(CircuitOpenError, match="20") as exc_info:
        harness.session.get(URL)

    assert "ZAMMAD_CIRCUIT_BREAKER_RECOVERY_TIMEOUT" in str(exc_info.value)
