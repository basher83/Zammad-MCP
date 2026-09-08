"""Resilient transport wrapper around the requests.Session that zammad-py uses for every call."""

from __future__ import annotations

import logging
import time
from functools import partial, partialmethod
from typing import Any

import requests  # type: ignore[import-untyped]

from mcp_zammad.resilience_config import ResilienceConfig
from mcp_zammad.resilience_retry import (
    RETRYABLE_EXCEPTIONS,
    SAFE_METHODS,
    Outcome,
    RetryExhaustedError,
    Sleeper,
    is_retryable,
    run_with_retries,
)
from mcp_zammad.resilience_state import CircuitBreaker, CircuitOpenError, Clock, RateLimiter

__all__ = ["CircuitOpenError", "ResilientSession", "RetryExhaustedError"]

logger = logging.getLogger(__name__)


class _Transport:
    """Single attempt against the wrapped session, gated by the client-side rate limiter."""

    def __init__(self, wrapped: Any, limiter: RateLimiter | None, sleep: Sleeper) -> None:
        self._wrapped = wrapped
        self._limiter = limiter
        self._sleep = sleep

    def send(self, method: str, url: str, kwargs: dict[str, Any]) -> Outcome:
        self._throttle()
        try:
            return self._wrapped.request(method, url, **kwargs), None
        except RETRYABLE_EXCEPTIONS as exc:
            logger.warning("Zammad request %s %s failed: %s", method, url, exc)
            return None, exc

    def _throttle(self) -> None:
        wait = self._limiter.acquire() if self._limiter is not None else 0.0
        if wait > 0:
            logger.info("Client-side rate limit reached; sleeping %.2fs before next Zammad request", wait)
            self._sleep(wait)


def _settle(breaker: CircuitBreaker, method: str, url: str, attempts: int, outcome: Outcome) -> requests.Response:
    """Record the terminal outcome on the breaker, then return the response or raise."""
    response, error = outcome
    if error is not None:
        breaker.record_failure()
        raise error
    if response is None:
        raise RuntimeError(f"{method} {url} produced neither a response nor an error")
    if not is_retryable(response):
        breaker.record_success()
        return response
    breaker.record_failure()
    if method not in SAFE_METHODS:
        return response
    raise RetryExhaustedError(f"{method} {url} failed after {attempts} attempts; last status {response.status_code}")


def _make_limiter(config: ResilienceConfig, clock: Clock) -> RateLimiter | None:
    if not config.rate_limit_enabled:
        return None
    return RateLimiter(config.rate_limit_requests, config.rate_limit_window, clock)


class ResilientSession:
    """Adds rate limiting, safe-method retries, and circuit breaking to a wrapped session."""

    def __init__(
        self, wrapped: Any, config: ResilienceConfig, *, clock: Clock = time.monotonic, sleeper: Sleeper = time.sleep
    ) -> None:
        self.wrapped = wrapped
        self._config = config
        self._sleep = sleeper
        self._transport = _Transport(wrapped, _make_limiter(config, clock), sleeper)
        self._breaker = CircuitBreaker(config.circuit_failure_threshold, config.circuit_recovery_timeout, clock)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.wrapped, name)

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Send a request; raises CircuitOpenError when open, RetryExhaustedError when safe retries run out."""
        self._breaker.check()
        method = method.upper()
        retries = self._config.max_retries if method in SAFE_METHODS else 0
        send = partial(self._transport.send, method, url, kwargs)
        outcome = run_with_retries(send, retries, self._config.retry_backoff_base, self._sleep)
        return _settle(self._breaker, method, url, retries + 1, outcome)

    get = partialmethod(request, "GET")
    post = partialmethod(request, "POST")
    put = partialmethod(request, "PUT")
    patch = partialmethod(request, "PATCH")
    delete = partialmethod(request, "DELETE")
