"""Retry policy for safe HTTP methods: which outcomes retry, how long to wait, and the attempt loop."""

from __future__ import annotations

from collections.abc import Callable

import requests  # type: ignore[import-untyped]

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
RETRYABLE_EXCEPTIONS = (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
MAX_RETRY_AFTER = 60.0

Outcome = tuple["requests.Response | None", "Exception | None"]
Send = Callable[[], Outcome]
Sleeper = Callable[[float], None]


class RetryExhaustedError(requests.exceptions.RequestException):
    """Raised when a safe request still fails after the configured retries."""


def is_retryable(response: requests.Response | None) -> bool:
    """True when the outcome (no response, or a transient status) warrants another attempt."""
    return response is None or response.status_code in RETRYABLE_STATUSES


def retry_after_seconds(response: requests.Response | None) -> float | None:
    """Return a bounded Retry-After delay in seconds, or None when absent or not delta-seconds."""
    header = response.headers.get("Retry-After") if response is not None else None
    if header is None:
        return None
    try:
        return min(max(float(header), 0.0), MAX_RETRY_AFTER)
    except ValueError:
        return None


def retry_delay(attempt: int, base: float, response: requests.Response | None) -> float:
    """Prefer the server's Retry-After; otherwise exponential backoff from `base`."""
    retry_after = retry_after_seconds(response)
    return retry_after if retry_after is not None else base * (2**attempt)


def run_with_retries(send: Send, retries: int, base: float, sleep: Sleeper) -> Outcome:
    """Call `send` up to retries + 1 times, sleeping between retryable outcomes."""
    response, error = send()
    for attempt in range(retries):
        if not is_retryable(response):
            break
        sleep(retry_delay(attempt, base, response))
        response, error = send()
    return response, error
