"""Integration tests for HTTP transport."""

import logging
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import httpx
import pytest

logger = logging.getLogger(__name__)


def start_mcp_server(
    env_overrides: dict[str, str] | None = None, *, env: dict[str, str] | None = None
) -> subprocess.Popen:
    """Start MCP server subprocess with environment overrides.

    Args:
        env_overrides: Environment variable overrides to apply to os.environ
        env: Pre-built environment dict (mutually exclusive with env_overrides)

    Returns:
        subprocess.Popen: Started server process
    """
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
def http_server() -> Iterator[str]:
    """Start HTTP server for integration testing."""
    # Start server process
    process = start_mcp_server(
        {
            "MCP_TRANSPORT": "http",
            "MCP_HOST": "127.0.0.1",
            "MCP_PORT": "8765",
            "ZAMMAD_URL": "http://mock.zammad.com/api/v1",
            "ZAMMAD_HTTP_TOKEN": "test-token",
        }
    )

    # Wait for server to become ready with polling
    server_url = "http://127.0.0.1:8765"
    max_wait = 5.0
    check_interval = 0.1
    elapsed = 0.0
    ready = False

    while elapsed < max_wait:
        try:
            # Try TCP connection to check if server is listening
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            result = sock.connect_ex(("127.0.0.1", 8765))
            sock.close()
            if result == 0:
                # TCP connection successful, verify HTTP endpoint
                try:
                    response = httpx.get(f"{server_url}/health", timeout=1.0)
                    if response.status_code == 200:
                        ready = True
                        break
                except Exception as e:
                    logger.debug("Startup poll: HTTP health check failed: %s", e)
        except Exception as e:
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
    """Test that MCP endpoint is accessible."""
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


@pytest.mark.integration
def test_http_server_rejects_missing_port():
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
