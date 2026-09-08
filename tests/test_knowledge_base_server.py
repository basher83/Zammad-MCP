"""Tests for the read-only knowledge-base MCP tools and resources.

Behavior is exercised through FastMCP's public ``call_tool``/``read_resource`` boundary
with the ZammadClient capability replaced by a controlled double.
"""

import json
from typing import Any
from unittest.mock import Mock

import pytest
import requests
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from mcp_zammad.knowledge_base import KnowledgeBaseNotFoundError
from mcp_zammad.server import ZammadMCPServer

KB_TOOLS = {
    "zammad_list_knowledge_bases",
    "zammad_get_knowledge_base",
    "zammad_get_kb_category",
    "zammad_list_kb_answers",
    "zammad_search_kb_answers",
    "zammad_get_kb_answer",
}


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


def _answer(body: str | None = None) -> dict[str, Any]:
    return {
        "id": 100,
        "knowledge_base_id": 1,
        "category_id": 10,
        "title": "Reset your password",
        "published_at": "2024-01-01T00:00:00Z",
        "internal_at": None,
        "archived_at": None,
        "promoted": False,
        "body": body,
    }


@pytest.fixture
def server() -> ZammadMCPServer:
    """Provide a server whose client capability is a Mock."""
    instance = ZammadMCPServer()
    instance.client = Mock()
    return instance


async def _call(server: ZammadMCPServer, tool: str, **params: Any) -> str:
    result = await server.mcp.call_tool(tool, {"params": params})
    return result.content[0].text  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_knowledge_base_tools_are_registered_read_only(server: ZammadMCPServer) -> None:
    tools = {tool.name: tool for tool in await server.mcp.list_tools()}

    assert KB_TOOLS.issubset(tools)
    for name in KB_TOOLS:
        assert tools[name].annotations is not None
        assert tools[name].annotations.readOnlyHint is True
        assert tools[name].annotations.destructiveHint is False
        assert tools[name].description is not None
        assert "Error Handling:" in tools[name].description


@pytest.mark.asyncio
async def test_list_knowledge_bases_markdown_and_json(server: ZammadMCPServer) -> None:
    server.client.list_knowledge_bases.return_value = [_kb()]

    markdown = await _call(server, "zammad_list_knowledge_bases")
    payload = json.loads(await _call(server, "zammad_list_knowledge_bases", response_format="json"))

    assert "Help" in markdown
    assert "(ID: 1)" in markdown
    assert payload["items"][0]["title"] == "Help"
    assert payload["count"] == 1


@pytest.mark.asyncio
async def test_list_knowledge_bases_reports_empty(server: ZammadMCPServer) -> None:
    server.client.list_knowledge_bases.return_value = []

    assert "No knowledge bases" in await _call(server, "zammad_list_knowledge_bases")


@pytest.mark.asyncio
async def test_get_knowledge_base_and_category(server: ZammadMCPServer) -> None:
    server.client.get_knowledge_base.return_value = _kb()
    server.client.get_kb_category.return_value = _category()

    kb_text = await _call(server, "zammad_get_knowledge_base", kb_id=1)
    category_text = await _call(server, "zammad_get_kb_category", kb_id=1, category_id=10)

    server.client.get_knowledge_base.assert_called_once_with(1)
    server.client.get_kb_category.assert_called_once_with(1, 10)
    assert "Help" in kb_text
    assert "Getting Started" in category_text
    assert "11" in category_text
    assert "100" in category_text


@pytest.mark.asyncio
async def test_list_and_search_kb_answers(server: ZammadMCPServer) -> None:
    server.client.list_kb_answers.return_value = [_answer()]
    server.client.search_kb_answers.return_value = [_answer()]

    listed = await _call(server, "zammad_list_kb_answers", kb_id=1, category_id=10)
    searched = json.loads(
        await _call(server, "zammad_search_kb_answers", kb_id=1, query="password", response_format="json")
    )

    server.client.list_kb_answers.assert_called_once_with(1, category_id=10)
    server.client.search_kb_answers.assert_called_once_with(1, "password")
    assert "Reset your password" in listed
    assert searched["items"][0]["id"] == 100


@pytest.mark.asyncio
async def test_search_kb_answers_reports_no_matches(server: ZammadMCPServer) -> None:
    server.client.search_kb_answers.return_value = []

    assert "No answers" in await _call(server, "zammad_search_kb_answers", kb_id=1, query="printer")


@pytest.mark.asyncio
async def test_get_kb_answer_includes_body(server: ZammadMCPServer) -> None:
    server.client.get_kb_answer.return_value = _answer(body="<p>Open settings</p>")

    markdown = await _call(server, "zammad_get_kb_answer", kb_id=1, answer_id=100)
    payload = json.loads(await _call(server, "zammad_get_kb_answer", kb_id=1, answer_id=100, response_format="json"))

    assert "Reset your password" in markdown
    assert "<p>Open settings</p>" in markdown
    assert payload["body"] == "<p>Open settings</p>"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "params"),
    [
        ("zammad_get_knowledge_base", {"kb_id": 0}),
        ("zammad_get_kb_answer", {"kb_id": 1, "answer_id": -1}),
        ("zammad_search_kb_answers", {"kb_id": 1, "query": "   "}),
        ("zammad_list_kb_answers", {"kb_id": 1, "unknown": True}),
    ],
)
async def test_invalid_parameters_are_rejected(server: ZammadMCPServer, tool: str, params: dict[str, Any]) -> None:
    with pytest.raises((ToolError, ValidationError)):
        await _call(server, tool, **params)
    assert not server.client.method_calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [requests.HTTPError("401 Unauthorized"), KnowledgeBaseNotFoundError("knowledge base 9 not found")],
)
async def test_client_failures_surface_as_tool_errors(server: ZammadMCPServer, error: Exception) -> None:
    server.client.get_knowledge_base.side_effect = error

    with pytest.raises(ToolError, match=str(error)):
        await _call(server, "zammad_get_knowledge_base", kb_id=9)
