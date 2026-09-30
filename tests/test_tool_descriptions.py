"""
Boundary tests for MCP tool descriptions.

MCP clients and agents read each tool description as its contract. These tests
check that the descriptions match what a client can observe through the public
FastMCP boundary: the input and output schemas, the JSON the tool returns, and
the errors it raises.
"""

import json
import re
import textwrap
from collections.abc import Iterator
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.types import Tool

from mcp_zammad.server import ZammadMCPServer

JSON_BLOCK = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)
STATED_DEFAULT = re.compile(r"^\s*-?\s*(\w+)\s*\([^)]*\)\s*:.*\(default:\s*([^)]+)\)", re.MULTILINE)
TIMESTAMPS = {"created_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z"}
USER_PAYLOAD = {"id": 5, "login": "u@example.com", "email": "u@example.com", "active": True, **TIMESTAMPS}
ORG_PAYLOAD = {"id": 2, "name": "ACME Corp", "member_ids": [5], "vip_level": "gold", **TIMESTAMPS}
DROPPED_USER_FIELDS = {"role_ids": [1, 2], "preferences": {"locale": "en-us"}}


@pytest.fixture
def zammad() -> Iterator[Mock]:
    double = Mock()
    double.get_current_user.return_value = {**USER_PAYLOAD, **DROPPED_USER_FIELDS}
    double.get_user.return_value = {**USER_PAYLOAD, **DROPPED_USER_FIELDS}
    double.get_organization.return_value = ORG_PAYLOAD
    with patch("mcp_zammad.server.ZammadClient", return_value=double):
        yield double


@pytest.fixture
def server(zammad: Mock) -> ZammadMCPServer:
    return ZammadMCPServer()


async def _tools(server: ZammadMCPServer) -> dict[str, Tool]:
    async with Client(server.mcp) as client:
        return {tool.name: tool for tool in await client.list_tools()}


async def _call_json(server: ZammadMCPServer, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with Client(server.mcp) as client:
        result = await client.call_tool(name, arguments)
    if result.structured_content and "result" not in result.structured_content:
        return result.structured_content
    return json.loads(result.content[0].text)  # type: ignore[union-attr]


def _json_examples(description: str) -> list[str]:
    return [textwrap.dedent(block) for block in JSON_BLOCK.findall(description)]


def _normalize(value: object) -> str:
    text = "none" if value is None else str(value)
    return text.strip().strip("`'\"").replace(",", "").replace("_", "").lower()


def _output_fields(schema: dict[str, Any]) -> set[str]:
    node = schema["properties"]["result"] if schema.get("x-fastmcp-wrap-result") else schema
    node = node.get("items", node)
    ref = node.get("$ref", "")
    node = schema.get("$defs", {}).get(ref.rsplit("/", 1)[-1], node) if ref else node
    return set(node.get("properties", {}))


@pytest.mark.asyncio
async def test_json_examples_in_tool_descriptions_are_valid_json(server: ZammadMCPServer) -> None:
    invalid = []
    for name, tool in (await _tools(server)).items():
        for example in _json_examples(tool.description or ""):
            try:
                json.loads(example)
            except json.JSONDecodeError as error:
                invalid.append(f"{name}: {error}")
    assert invalid == []


@pytest.mark.asyncio
async def test_json_example_fields_exist_in_the_output_schema(server: ZammadMCPServer) -> None:
    unknown = {}
    for name, tool in (await _tools(server)).items():
        fields = _output_fields(tool.outputSchema or {})
        examples = [json.loads(example) for example in _json_examples(tool.description or "")]
        items = [example[0] if isinstance(example, list) else example for example in examples]
        extra = sorted({key for item in items for key in item} - fields) if fields else []
        if extra:
            unknown[name] = extra
    assert unknown == {}


@pytest.mark.asyncio
async def test_stated_defaults_match_the_input_schema(server: ZammadMCPServer) -> None:
    stated_defaults = [
        (f"{name}.{param}", stated, tool.inputSchema.get("properties", {}).get(param, {}))
        for name, tool in (await _tools(server)).items()
        for param, stated in STATED_DEFAULT.findall(tool.description or "")
    ]
    mismatched = {
        key: (stated, schema["default"])
        for key, stated, schema in stated_defaults
        if "default" in schema and _normalize(stated) != _normalize(schema["default"])
    }
    assert mismatched == {}


@pytest.mark.asyncio
async def test_tools_raise_errors_instead_of_returning_error_strings(server: ZammadMCPServer, zammad: Mock) -> None:
    zammad.get_user.side_effect = RuntimeError("404 Not Found")
    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="404 Not Found"):
            await client.call_tool("zammad_get_user", {"user_id": 5})
    tools = await _tools(server)
    advertised = [name for name, tool in tools.items() if 'Returns "Error:' in (tool.description or "")]
    assert advertised == []


@pytest.mark.asyncio
async def test_export_description_states_the_export_dir_requirement(
    server: ZammadMCPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ZAMMAD_EXPORT_DIR", raising=False)
    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="ZAMMAD_EXPORT_DIR is not set"):
            await client.call_tool("zammad_export_tickets", {"output_path": "out.jsonl"})
    description = (await _tools(server))["zammad_export_tickets"].description or ""
    assert re.search(r"ZAMMAD_EXPORT_DIR[^.]*\b(?:not set|unset)\b", description)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("zammad_get_user", {"user_id": 5, "response_format": "json"}),
        ("zammad_get_current_user", {}),
        ("zammad_get_organization", {"org_id": 2, "response_format": "json"}),
    ],
)
async def test_descriptions_do_not_promise_fields_the_output_drops(
    server: ZammadMCPServer, tool: str, arguments: dict[str, Any]
) -> None:
    output = await _call_json(server, tool, arguments)
    description = ((await _tools(server))[tool].description or "").lower()
    promised = {"roles", "preferences", "contact_info", "custom fields"}
    missing = sorted(field for field in promised if field in description and field not in output)
    assert missing == []


MAX_DESCRIPTION_CHARS = 600
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
TOOL_NAME = re.compile(r"\bzammad_[a-z_]+\b")


@pytest.mark.asyncio
async def test_every_description_adds_guidance_beyond_the_summary(server: ZammadMCPServer) -> None:
    tools = await _tools(server)
    summary_only = sorted(
        name for name, tool in tools.items() if len(SENTENCE_END.split((tool.description or "").strip())) < 2
    )
    assert summary_only == []


@pytest.mark.asyncio
async def test_descriptions_stay_within_the_context_budget(server: ZammadMCPServer) -> None:
    tools = await _tools(server)
    oversized = {
        name: len(tool.description or "")
        for name, tool in tools.items()
        if len(tool.description or "") > MAX_DESCRIPTION_CHARS
    }
    assert oversized == {}


@pytest.mark.asyncio
async def test_descriptions_only_reference_registered_tools(server: ZammadMCPServer) -> None:
    tools = await _tools(server)
    unknown = {
        name: sorted(set(TOOL_NAME.findall(tool.description or "")) - set(tools)) for name, tool in tools.items()
    }
    assert {name: refs for name, refs in unknown.items() if refs} == {}
