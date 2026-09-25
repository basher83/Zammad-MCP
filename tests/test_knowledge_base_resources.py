"""Tests for the ``zammad://kb/...`` MCP resources through FastMCP's public boundary."""

from typing import Any
from unittest.mock import Mock

import pytest
import requests
from fastmcp.exceptions import ResourceError

from mcp_zammad.server import ZammadMCPServer


def _kb() -> dict[str, Any]:
    return {"id": 1, "title": "Help", "active": True, "root_category_ids": [10], "category_count": 2, "answer_count": 2}


def _category() -> dict[str, Any]:
    return {
        "id": 10,
        "knowledge_base_id": 1,
        "parent_id": None,
        "title": "Getting Started",
        "child_category_ids": [11],
        "answer_ids": [100],
    }


def _answer() -> dict[str, Any]:
    return {"id": 100, "knowledge_base_id": 1, "category_id": 10, "title": "Reset", "body": "<p>Open settings</p>"}


@pytest.fixture
def server() -> ZammadMCPServer:
    """Provide a server whose client capability is a Mock."""
    instance = ZammadMCPServer()
    instance.client = Mock()
    return instance


@pytest.mark.asyncio
async def test_knowledge_base_resources(server: ZammadMCPServer) -> None:
    server.client.get_knowledge_base.return_value = _kb()
    server.client.get_kb_category.return_value = _category()
    server.client.get_kb_answer.return_value = _answer()

    kb = await server.mcp.read_resource("zammad://kb/1")
    category = await server.mcp.read_resource("zammad://kb/1/category/10")
    answer = await server.mcp.read_resource("zammad://kb/1/answer/100")

    assert "Help" in str(kb.contents[0].content)
    assert "Getting Started" in str(category.contents[0].content)
    assert "<p>Open settings</p>" in str(answer.contents[0].content)


@pytest.mark.asyncio
async def test_knowledge_base_resource_failures_surface_as_errors(server: ZammadMCPServer) -> None:
    server.client.get_kb_answer.side_effect = requests.HTTPError("500 Server Error")

    with pytest.raises(ResourceError, match="500 Server Error"):
        await server.mcp.read_resource("zammad://kb/1/answer/100")
