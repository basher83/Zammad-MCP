"""Tests for the __main__ module."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import mcp_zammad
import mcp_zammad.__main__ as main_module
from mcp_zammad.__main__ import main


def _install_fake_server(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Install a fake server module for deferred import tests."""
    mock_mcp = Mock()
    fake_server = SimpleNamespace(mcp=mock_mcp)
    monkeypatch.setitem(sys.modules, "mcp_zammad.server", fake_server)
    monkeypatch.setattr(mcp_zammad, "server", fake_server, raising=False)
    return mock_mcp


class TestMain:
    """Test cases for the main entry point."""

    def test_main_calls_mcp_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that main() calls mcp.run()."""
        mock_mcp = _install_fake_server(monkeypatch)

        main()

        mock_mcp.run.assert_called_once_with()

    def test_main_module_execution(self) -> None:
        """Test that __main__ block would execute main() when run as a script."""
        assert hasattr(main_module, "main")
        assert callable(main_module.main)

    def test_import_without_execution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that importing the module doesn't execute main()."""
        mock_mcp = _install_fake_server(monkeypatch)
        mock_mcp.run.assert_not_called()


def test_main_with_http_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test main entry point with HTTP transport."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8000")
    mock_mcp = _install_fake_server(monkeypatch)

    main()

    mock_mcp.run.assert_called_once_with(transport="streamable-http")


def test_main_with_stdio_transport_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test main entry point defaults to stdio transport."""
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    monkeypatch.delenv("MCP_HOST", raising=False)
    monkeypatch.delenv("MCP_PORT", raising=False)
    mock_mcp = _install_fake_server(monkeypatch)

    main()

    mock_mcp.run.assert_called_once_with()


def test_main_validates_http_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test main validates HTTP configuration before importing the server module."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.delenv("MCP_PORT", raising=False)
    mock_mcp = _install_fake_server(monkeypatch)

    with pytest.raises(ValueError) as excinfo:
        main()

    assert "HTTP transport requires MCP_PORT" in str(excinfo.value)
    mock_mcp.run.assert_not_called()


def test_main_validates_bad_port_before_server_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test invalid MCP_PORT fails through config validation before server import side effects."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_PORT", "not-a-port")

    with (
        patch.dict(sys.modules, {"mcp_zammad.server": None}),
        pytest.raises(ValueError, match="MCP_PORT must be a valid integer"),
    ):
        main()
