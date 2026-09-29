"""Deterministic doubles for exercising the resilient session boundary."""

from typing import Any

import requests

from mcp_zammad.resilience import ResilientSession
from mcp_zammad.resilience_config import ResilienceConfig

URL = "https://zammad.example.com/api/v1/tickets"


def make_response(status: int, headers: dict[str, str] | None = None) -> requests.Response:
    """Build a real requests.Response with the given status and headers."""
    response = requests.Response()
    response.status_code = status
    response.headers.update(headers or {})
    response._content = b"{}"
    return response


class FakeClock:
    """Injectable monotonic clock."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeSession:
    """Scripted stand-in for requests.Session; outcomes are responses or exceptions."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, str]] = []
        self.headers: dict[str, str] = {}
        self.verify = True
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self.calls.append((method, url))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def close(self) -> None:
        self.closed = True


class Harness:
    """Bundle of the wrapper under test and its observable capability doubles."""

    def __init__(self, outcomes: list[Any], clock: FakeClock | None = None, **overrides: Any) -> None:
        self.inner = FakeSession(outcomes)
        self.clock = clock or FakeClock()
        self.sleeps: list[float] = []
        config = ResilienceConfig(**overrides)
        self.session = ResilientSession(self.inner, config, clock=self.clock, sleeper=self._sleep)

    def _sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.clock.advance(seconds)

    @property
    def calls(self) -> list[tuple[str, str]]:
        return self.inner.calls
