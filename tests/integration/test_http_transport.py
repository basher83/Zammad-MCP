"""Integration tests for HTTP transport."""

import os
import time
import subprocess
import httpx
import pytest


@pytest.fixture
def http_server():
    """Start HTTP server for integration testing."""
    env = os.environ.copy()
    env.update({
        "MCP_TRANSPORT": "http",
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": "8765",
        "ZAMMAD_URL": "http://mock.zammad.com/api/v1",
        "ZAMMAD_HTTP_TOKEN": "test-token",
    })

    # Start server process
    process = subprocess.Popen(
        ["python", "-m", "mcp_zammad"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    time.sleep(2)

    yield "http://127.0.0.1:8765"

    # Cleanup
    process.terminate()
    process.wait(timeout=5)


@pytest.mark.integration
def test_http_server_starts(http_server):
    """Test that HTTP server starts and responds."""
    response = httpx.get(f"{http_server}/health", timeout=5.0)
    assert response.status_code == 200


@pytest.mark.integration
def test_mcp_endpoint_exists(http_server):
    """Test that MCP endpoint is accessible."""
    # MCP endpoint should accept POST requests
    response = httpx.post(
        f"{http_server}/mcp/",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        headers={"Accept": "application/json, text/event-stream"},
        timeout=10.0,
    )
    # 307 = Temporary Redirect (to SSE endpoint), other codes indicate response
    assert response.status_code in [200, 307, 400, 405]  # Server should respond


@pytest.mark.integration
def test_http_server_rejects_missing_port():
    """Test that server fails without port in HTTP mode."""
    env = os.environ.copy()
    env.update({
        "MCP_TRANSPORT": "http",
        "MCP_HOST": "127.0.0.1",
    })
    env.pop("MCP_PORT", None)  # Remove port

    process = subprocess.Popen(
        ["python", "-m", "mcp_zammad"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Should exit with error
    process.wait(timeout=5)
    assert process.returncode != 0

    stderr = process.stderr.read().decode()
    assert "HTTP transport requires MCP_PORT" in stderr
