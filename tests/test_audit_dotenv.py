"""Tests that audit settings supplied only through a ``.env`` file take effect."""

import json
import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client

from mcp_zammad.audit import AuditConfigError
from mcp_zammad.server import ZammadMCPServer

AUDIT_VARS = ("ZAMMAD_AUDIT_LOG_ENABLED", "ZAMMAD_AUDIT_LOG_DESTINATION", "ZAMMAD_AUDIT_LOG_FILE")
GROUP = {"id": 1, "name": "Users", "created_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z"}


@pytest.fixture
def dotenv_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Run in an isolated cwd with no audit variables exported; restore os.environ afterwards."""
    for name in AUDIT_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ):
        yield tmp_path


@pytest.mark.asyncio
async def test_audit_enabled_via_dotenv_records_tool_call(dotenv_cwd: Path) -> None:
    audit_file = dotenv_cwd / "audit.jsonl"
    (dotenv_cwd / ".env").write_text(
        f"ZAMMAD_AUDIT_LOG_ENABLED=true\nZAMMAD_AUDIT_LOG_DESTINATION=file\nZAMMAD_AUDIT_LOG_FILE={audit_file}\n"
    )
    with patch("mcp_zammad.server.ZammadClient") as mock_class:
        mock_class.return_value = Mock(get_groups=Mock(return_value=[GROUP]))
        server = ZammadMCPServer()
        async with Client(server.mcp) as client:
            await client.call_tool("zammad_list_groups", {})

    assert server.audit.enabled
    records = [json.loads(line) for line in audit_file.read_text().splitlines()]
    assert [r["action"] for r in records if r["event_type"] == "tool_call"] == ["zammad_list_groups"]


def test_invalid_dotenv_audit_config_fails_at_startup(dotenv_cwd: Path) -> None:
    (dotenv_cwd / ".env").write_text("ZAMMAD_AUDIT_LOG_ENABLED=true\nZAMMAD_AUDIT_LOG_DESTINATION=file\n")

    with pytest.raises(AuditConfigError):
        ZammadMCPServer()
