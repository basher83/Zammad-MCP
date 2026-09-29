"""Integration tests for HTTP transport."""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest
from fastmcp import Client

logger = logging.getLogger(__name__)

WEBHOOK_SIGNING_KEY = "integration-test-hmac-key"  # not a real credential


def signed_delivery(payload: dict, secret: str = WEBHOOK_SIGNING_KEY) -> tuple[bytes, dict[str, str]]:
    """Build a Zammad-style webhook body and HMAC-SHA1 ``X-Hub-Signature`` header."""
    body = json.dumps(payload).encode()
    signature = "sha1=" + hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    return body, {"Content-Type": "application/json", "X-Hub-Signature": signature}


def start_mcp_server(
    env_overrides: dict[str, str] | None = None, *, env: dict[str, str] | None = None
) -> subprocess.Popen:
    """Start MCP server subprocess with environment overrides.

    Args:
        env_overrides: Environment variable overrides to apply to os.environ
        env: Pre-built environment dict (mutually exclusive with env_overrides)

    Returns:
        subprocess.Popen: Started server process

    Raises:
        ValueError: If both env and env_overrides are provided
    """
    if env is not None and env_overrides is not None:
        msg = "env and env_overrides are mutually exclusive - provide only one"
        raise ValueError(msg)

    if env is None:
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)

    return subprocess.Popen(
        [sys.executable, "-m", "mcp_zammad"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def terminate_process_safely(process: subprocess.Popen, timeout: float = 5.0) -> None:
    """Safely terminate a subprocess with proper timeout handling.

    Args:
        process: The process to terminate
        timeout: Timeout in seconds for waiting for process termination
    """
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning("Process did not terminate within %s seconds, killing...", timeout)
        process.kill()
        # Wait without timeout to collect exit code
        process.wait()


@pytest.fixture
def mock_zammad_server() -> Iterator[str]:
    """Start a minimal fake Zammad server that handles startup verification."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/v1/users/me":
                body = json.dumps({"id": 1, "login": "test-integration", "name": "Test User"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt: str, *args: object) -> None:
            pass  # Suppress noisy request logs during tests

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/api/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def http_server(mock_zammad_server: str) -> Iterator[str]:
    """Start HTTP server for integration testing."""
    # Get an available ephemeral port
    temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    temp_sock.bind(("127.0.0.1", 0))
    port = temp_sock.getsockname()[1]
    temp_sock.close()

    # Start server process with dynamically allocated port
    process = start_mcp_server(
        {
            "MCP_TRANSPORT": "http",
            "MCP_HOST": "127.0.0.1",
            "MCP_PORT": str(port),
            "ZAMMAD_URL": mock_zammad_server,
            "ZAMMAD_HTTP_TOKEN": "test-token",
            "ZAMMAD_WEBHOOK_SECRET": WEBHOOK_SIGNING_KEY,
        }
    )

    # Wait for server to become ready with polling
    server_url = f"http://127.0.0.1:{port}"
    max_wait = 5.0
    check_interval = 0.1
    elapsed = 0.0
    ready = False

    while elapsed < max_wait:
        try:
            # Try TCP connection to check if server is listening
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            if result == 0:
                # TCP connection successful, verify HTTP endpoint
                try:
                    response = httpx.get(f"{server_url}/health", timeout=1.0)
                    if response.status_code == 200:
                        ready = True
                        break
                except httpx.RequestError as e:
                    logger.debug("Startup poll: HTTP health check failed: %s", e)
        except OSError as e:
            logger.debug("Startup poll: TCP connect failed: %s", e)

        time.sleep(check_interval)
        elapsed += check_interval

    if not ready:
        terminate_process_safely(process)
        raise TimeoutError(f"Server did not become ready within {max_wait}s")

    try:
        yield server_url
    finally:
        # Cleanup
        terminate_process_safely(process)


@pytest.mark.integration
def test_http_server_starts(http_server) -> None:
    """Test that HTTP server starts and responds."""
    response = httpx.get(f"{http_server}/health", timeout=5.0)
    assert response.status_code == 200


@pytest.mark.integration
def test_mcp_endpoint_exists(http_server) -> None:
    """Test that MCP endpoint is accessible and redirects correctly."""
    # MCP endpoint should accept POST requests
    # FastMCP HTTP transport returns 307 redirect to SSE endpoint
    response = httpx.post(
        f"{http_server}/mcp/",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        headers={"Accept": "application/json"},
        timeout=10.0,
        follow_redirects=False,
    )
    # MCP HTTP transport redirects to SSE endpoint, 307 indicates endpoint exists
    assert response.status_code == 307

    # Verify redirect target
    location = response.headers.get("Location")
    assert location is not None, "Location header must be present in 307 redirect"
    # FastMCP redirects from /mcp/ (with slash) to /mcp (without slash)
    assert location.endswith("/mcp"), f"Expected redirect to /mcp endpoint, got: {location}"


@pytest.mark.integration
def test_webhook_delivery_is_retrievable_through_mcp(http_server) -> None:
    """Signed deliveries are accepted, unsigned ones rejected, and events are listable via MCP."""
    first, first_headers = signed_delivery({"ticket": {"id": 501, "number": "10501"}})
    second, second_headers = signed_delivery({"ticket": {"id": 502, "article_count": 4}, "article": {"id": 9}})
    forged, forged_headers = signed_delivery({"ticket": {"id": 503}}, secret="not-the-secret")

    assert httpx.post(f"{http_server}/webhooks/zammad", content=first, headers=first_headers).status_code == 202
    assert httpx.post(f"{http_server}/webhooks/zammad", content=second, headers=second_headers).status_code == 202
    assert httpx.post(f"{http_server}/webhooks/zammad", content=forged, headers=forged_headers).status_code == 401

    async def list_events() -> dict:
        async with Client(f"{http_server}/mcp") as client:
            result = await client.call_tool("zammad_list_events", {"params": {"limit": 10}})
        return result.structured_content

    data = asyncio.run(list_events())
    assert [(e["event_type"], e["ticket_id"]) for e in data["events"]] == [
        ("ticket.update", 501),
        ("ticket.article.create", 502),
    ]
    assert data["events"][1]["article_id"] == 9
    assert data["retained_total"] == 2


@pytest.mark.integration
def test_http_server_rejects_missing_port() -> None:
    """Test that server fails without port in HTTP mode."""
    env = os.environ.copy()
    env.update(
        {
            "MCP_TRANSPORT": "http",
            "MCP_HOST": "127.0.0.1",
        }
    )
    env.pop("MCP_PORT", None)  # Remove port

    process = start_mcp_server(env=env)

    # Should exit with error
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired as exc:
        # Process hung - terminate and kill if needed
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        # Assert failure - process should have exited quickly with error
        msg = "Process did not exit within timeout"
        raise AssertionError(msg) from exc

    assert process.returncode != 0

    assert process.stderr is not None
    stderr = process.stderr.read().decode()
    assert "HTTP transport requires MCP_PORT" in stderr
