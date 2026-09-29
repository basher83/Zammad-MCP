"""Process-local rate limiter and circuit breaker state driven by an injected monotonic clock."""

from __future__ import annotations

import threading
from collections.abc import Callable

import requests  # type: ignore[import-untyped]

Clock = Callable[[], float]


class CircuitOpenError(requests.exceptions.RequestException):
    """Raised without contacting Zammad while the circuit breaker is open."""


class RateLimiter:
    """Fixed-window limiter: at most `limit` attempts per `window` seconds."""

    def __init__(self, limit: int, window: float, clock: Clock) -> None:
        self._limit = limit
        self._window = window
        self._clock = clock
        self._lock = threading.Lock()
        self._window_start = clock()
        self._count = 0

    def acquire(self) -> float:
        """Reserve one attempt and return how long the caller must sleep before sending it."""
        with self._lock:
            now = self._clock()
            if now - self._window_start >= self._window:
                self._window_start, self._count = now, 0
            if self._count < self._limit:
                self._count += 1
                return 0.0
            wait = self._window_start + self._window - now
            self._window_start, self._count = now + wait, 1
            return wait


class CircuitBreaker:
    """Closed → open after `threshold` terminal failures; half-open probe after `recovery_timeout`."""

    def __init__(self, threshold: int, recovery_timeout: float, clock: Clock) -> None:
        self._threshold = threshold
        self._recovery_timeout = recovery_timeout
        self._clock = clock
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at: float | None = None

    def check(self) -> None:
        """Raise CircuitOpenError while open; allow one probe once the recovery timeout has elapsed."""
        with self._lock:
            if self._opened_at is None:
                return
            remaining = self._opened_at + self._recovery_timeout - self._clock()
            if remaining > 0:
                raise CircuitOpenError(_open_message(self._failures, remaining, self._recovery_timeout))
            self._opened_at = None

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._threshold:
                self._opened_at = self._clock()


def _open_message(failures: int, remaining: float, recovery_timeout: float) -> str:
    return (
        f"Zammad circuit breaker is open after {failures} consecutive failures; "
        f"retry in {remaining:.1f}s (ZAMMAD_CIRCUIT_BREAKER_RECOVERY_TIMEOUT={recovery_timeout:g})"
    )
