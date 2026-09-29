"""Annotation contract for the host-side ticket export tool."""

import pytest

from mcp_zammad.server import ZammadMCPServer


@pytest.mark.asyncio
async def test_export_tool_is_annotated_as_a_write():
    """Exporting appends JSONL files on the host, so the tool must not claim to be read-only."""
    server = ZammadMCPServer()

    tools = {tool.name: tool for tool in await server.mcp.list_tools()}
    annotations = tools["zammad_export_tickets"].annotations

    assert annotations.readOnlyHint is False
    assert annotations.destructiveHint is False
