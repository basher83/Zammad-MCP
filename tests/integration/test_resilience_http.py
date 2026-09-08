"""Integration test: a real zammad-py session recovers from throttling via a fake Zammad server."""

import json
import os
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest

from mcp_zammad.client import ZammadClient


class _ThrottlingZammad:
    """Fake Zammad that answers 429, then 503, then succeeds for /users/me."""

    def __init__(self) -> None:
        self.statuses = [429, 503, 200]
        self.hits: list[str] = []

    def handler(self) -> type[BaseHTTPRequestHandler]:
        fake = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                fake.hits.append(self.path)
                status = fake.statuses.pop(0) if fake.statuses else 200
                body = json.dumps({"id": 1, "login": "resilient"}).encode() if status == 200 else b"{}"
                self.send_response(status)
                if status == 429:
                    self.send_header("Retry-After", "0")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt: str, *args: object) -> None:
                pass

        return _Handler


@pytest.fixture
def throttling_zammad() -> Iterator[tuple[str, _ThrottlingZammad]]:
    fake = _ThrottlingZammad()
    server = HTTPServer(("127.0.0.1", 0), fake.handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/api/v1", fake
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.integration
def test_read_recovers_after_throttled_responses(throttling_zammad: tuple[str, _ThrottlingZammad]) -> None:
    url, fake = throttling_zammad
    env = {"ZAMMAD_URL": url, "ZAMMAD_HTTP_TOKEN": "test-token", "ZAMMAD_RETRY_BACKOFF_BASE": "0.01"}

    with patch.dict(os.environ, env, clear=True):
        user = ZammadClient().get_current_user()

    assert user["login"] == "resilient"
    assert fake.hits == ["/api/v1/users/me"] * 3
