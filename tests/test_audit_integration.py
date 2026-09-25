"""Tests for audit events emitted at the server and client boundaries (issue #121)."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mcp_zammad.audit import AuditConfig, AuditLogger
from mcp_zammad.client import ZammadClient
from mcp_zammad.server import ZammadMCPServer

GROUP = {"id": 1, "name": "Users", "created_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z"}


@pytest.fixture
def audit_file(tmp_path: Path) -> Path:
    return tmp_path / "audit.jsonl"


@pytest.fixture
def audit(audit_file: Path) -> AuditLogger:
    env = {
        "ZAMMAD_AUDIT_LOG_ENABLED": "true",
        "ZAMMAD_AUDIT_LOG_DESTINATION": "file",
        "ZAMMAD_AUDIT_LOG_FILE": str(audit_file),
    }
    return AuditLogger(AuditConfig.from_env(env))


@pytest.fixture
def fake_zammad():
    """Replace the Zammad client at the server boundary with a controlled double."""
    with patch("mcp_zammad.server.ZammadClient") as mock_class:
        instance = Mock()
        instance.get_current_user.return_value = {"id": 1, "email": "agent@example.com"}
        instance.get_groups.return_value = [GROUP]
        mock_class.return_value = instance
        yield instance, mock_class


def _records(path: Path, event_type: str | None = None) -> list[dict]:
    if not path.exists():
        return []
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [r for r in records if event_type is None or r["event_type"] == event_type]


@pytest.mark.asyncio
async def test_successful_tool_call_emits_one_audit_record(fake_zammad, audit: AuditLogger, audit_file: Path) -> None:
    server = ZammadMCPServer(audit_logger=audit)

    async with Client(server.mcp) as client:
        result = await client.call_tool("zammad_list_groups", {"params": {}})

    assert "Users" in result.content[0].text
    records = _records(audit_file, "tool_call")
    assert len(records) == 1
    assert records[0]["action"] == "zammad_list_groups"
    assert records[0]["success"] is True
    assert records[0]["duration_ms"] >= 0
    assert records[0]["details"] == {}


@pytest.mark.asyncio
async def test_failed_tool_call_records_failure_and_reraises(fake_zammad, audit: AuditLogger, audit_file: Path) -> None:
    instance, _ = fake_zammad
    instance.get_groups.side_effect = RuntimeError("token=leaked-secret")
    server = ZammadMCPServer(audit_logger=audit)

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("zammad_list_groups", {"params": {}})

    records = _records(audit_file, "tool_call")
    assert len(records) == 1
    assert records[0]["success"] is False
    assert records[0]["details"] == {"error_type": "RuntimeError"}
    assert "leaked-secret" not in audit_file.read_text()


@pytest.mark.asyncio
async def test_disabled_audit_keeps_tool_behavior_and_silence(fake_zammad, audit_file: Path) -> None:
    disabled = AuditLogger(AuditConfig.from_env({"ZAMMAD_AUDIT_LOG_FILE": str(audit_file)}))
    server = ZammadMCPServer(audit_logger=disabled)

    async with Client(server.mcp) as client:
        result = await client.call_tool("zammad_list_groups", {"params": {}})

    assert "Users" in result.content[0].text
    assert not audit_file.exists()


def test_server_builds_audit_logger_from_environment(audit_file: Path) -> None:
    env = {
        "ZAMMAD_AUDIT_LOG_ENABLED": "true",
        "ZAMMAD_AUDIT_LOG_DESTINATION": "file",
        "ZAMMAD_AUDIT_LOG_FILE": str(audit_file),
    }
    with patch.dict(os.environ, env):
        server = ZammadMCPServer()

    server.audit.log_event("tool_call", "probe", success=True)
    assert [r["action"] for r in _records(audit_file)] == ["probe"]


@patch("mcp_zammad.client.ZammadAPI")
def test_private_url_emits_redacted_security_event(mock_api: MagicMock, audit: AuditLogger, audit_file: Path) -> None:
    url = "http://user:pw@192.168.1.100/api/v1?token=abc"
    with patch.dict(os.environ, {"ZAMMAD_URL": url, "ZAMMAD_HTTP_TOKEN": "tok"}, clear=True):
        ZammadClient(audit_logger=audit)

    records = _records(audit_file, "security_validation")
    assert len(records) == 1
    assert records[0]["success"] is False
    assert records[0]["details"] == {"reason": "private_network", "host": "192.168.1.100"}
    text = audit_file.read_text()
    for leaked in ("user:pw", "token=abc", "tok"):
        assert leaked not in text


@patch("mcp_zammad.client.ZammadAPI")
def test_localhost_url_emits_security_event(mock_api: MagicMock, audit: AuditLogger, audit_file: Path) -> None:
    with patch.dict(os.environ, {"ZAMMAD_URL": "http://localhost:3000", "ZAMMAD_HTTP_TOKEN": "tok"}, clear=True):
        ZammadClient(audit_logger=audit)

    records = _records(audit_file, "security_validation")
    assert [r["details"]["reason"] for r in records] == ["local_host"]


@patch("mcp_zammad.client.ZammadAPI")
def test_public_url_emits_no_security_event(mock_api: MagicMock, audit: AuditLogger, audit_file: Path) -> None:
    with patch.dict(os.environ, {"ZAMMAD_URL": "https://zammad.example.com", "ZAMMAD_HTTP_TOKEN": "tok"}, clear=True):
        ZammadClient(audit_logger=audit)

    assert _records(audit_file) == []


@pytest.mark.asyncio
async def test_initialize_audits_authentication_success(fake_zammad, audit: AuditLogger, audit_file: Path) -> None:
    _, mock_class = fake_zammad
    server = ZammadMCPServer(audit_logger=audit)

    await server.initialize()

    assert mock_class.call_args.kwargs["audit_logger"] is audit
    records = _records(audit_file, "authentication")
    assert records == [{**records[0], "success": True, "details": {"user_id": 1}}]


@pytest.mark.asyncio
async def test_initialize_audits_authentication_failure(audit: AuditLogger, audit_file: Path) -> None:
    server = ZammadMCPServer(audit_logger=audit)

    with (
        patch("mcp_zammad.server.ZammadClient", side_effect=RuntimeError("password=oops")),
        pytest.raises(RuntimeError),
    ):
        await server.initialize()

    records = _records(audit_file, "authentication")
    assert len(records) == 1
    assert records[0]["success"] is False
    assert records[0]["details"] == {"error_type": "RuntimeError"}
    assert "oops" not in audit_file.read_text()
