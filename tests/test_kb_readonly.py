"""Tests for the read-only Knowledge Base feature (PR1).

Scope:
- ZammadClient KB read-only methods (mocked HTTP).
- ZammadAPIError typed-error semantics.
- MCP tool error semantics: failures must propagate as exceptions, not as
  successful string payloads.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_zammad.client import ZammadAPIError, ZammadClient
from mcp_zammad.server import (
    _format_kb_answer_markdown,
    _format_kb_category_markdown,
    _format_kb_markdown,
    _kb_answer_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    status_code: int = 200,
    json_body: Any = None,
    *,
    content: bytes | None = None,
    url: str = "https://zammad.example/api/v1/knowledge_bases",
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.ok = 200 <= status_code < 300
    response.url = url
    if json_body is None and content is None:
        response.content = b""
    else:
        response.content = content if content is not None else json.dumps(json_body).encode()
    if json_body is None and content is None:
        response.json.side_effect = ValueError("no body")
    else:
        response.json.return_value = json_body
    return response


@pytest.fixture
def kb_client() -> ZammadClient:
    """Return a ZammadClient instance with credentials patched in env."""
    with patch.dict(
        "os.environ",
        {"ZAMMAD_URL": "https://zammad.example/api/v1/", "ZAMMAD_HTTP_TOKEN": "tok"},
        clear=False,
    ):
        client = ZammadClient()
    # Replace the underlying session with a MagicMock for full HTTP control.
    client.api.session = MagicMock()
    # zammad_py exposes api.url as the base URL with a trailing slash.
    client.api.url = "https://zammad.example/api/v1/"
    return client


# ---------------------------------------------------------------------------
# ZammadAPIError + _kb_raise_or_return
# ---------------------------------------------------------------------------


class TestZammadAPIErrorAndRaise:
    def test_raise_on_4xx_with_json_body(self, kb_client: ZammadClient) -> None:
        resp = _make_response(403, {"error": "Forbidden"})
        with pytest.raises(ZammadAPIError) as exc:
            kb_client._kb_raise_or_return(resp)
        assert exc.value.status_code == 403
        assert exc.value.body == {"error": "Forbidden"}

    def test_raise_on_5xx_with_text_body(self, kb_client: ZammadClient) -> None:
        resp = _make_response(500, content=b"server boom")
        resp.json.side_effect = ValueError("no json")
        resp.text = "server boom"
        with pytest.raises(ZammadAPIError) as exc:
            kb_client._kb_raise_or_return(resp)
        assert exc.value.status_code == 500
        assert exc.value.body == "server boom"

    def test_204_returns_empty_dict(self, kb_client: ZammadClient) -> None:
        resp = _make_response(204)
        assert kb_client._kb_raise_or_return(resp) == {}


# ---------------------------------------------------------------------------
# list_knowledge_bases
# ---------------------------------------------------------------------------


class TestListKnowledgeBases:
    def test_returns_list_directly(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(
            200, [{"id": 1}, {"id": 2}]
        )
        assert kb_client.list_knowledge_bases() == [{"id": 1}, {"id": 2}]

    def test_wraps_single_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(200, {"id": 1})
        assert kb_client.list_knowledge_bases() == [{"id": 1}]

    def test_404_falls_back_to_id_probing(self, kb_client: ZammadClient) -> None:
        responses = [_make_response(404)]
        responses += [_make_response(200, {"id": 1})]
        responses += [_make_response(404)] * 9  # IDs 2-10 not found
        kb_client.api.session.get.side_effect = responses
        assert kb_client.list_knowledge_bases() == [{"id": 1}]

    def test_401_raises_typed_error(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(
            401, {"error": "Unauthorized"}
        )
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.list_knowledge_bases()
        assert exc.value.status_code == 401

    def test_500_raises_typed_error(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(500, {"error": "boom"})
        with pytest.raises(ZammadAPIError):
            kb_client.list_knowledge_bases()

    def test_empty_body_raises_instead_of_silent_fallback(
        self, kb_client: ZammadClient
    ) -> None:
        resp = _make_response(200)  # 200 with empty content
        kb_client.api.session.get.return_value = resp
        with pytest.raises(ZammadAPIError):
            kb_client.list_knowledge_bases()

    def test_unexpected_shape_raises(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(200, "weird")
        with pytest.raises(ZammadAPIError):
            kb_client.list_knowledge_bases()

    def test_probe_propagates_non_404_errors(self, kb_client: ZammadClient) -> None:
        # GET /knowledge_bases -> 404, then probing ID 1 -> 401 (auth error).
        responses = [_make_response(404), _make_response(401, {"error": "auth"})]
        kb_client.api.session.get.side_effect = responses
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.list_knowledge_bases()
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# get_knowledge_base / get_kb_category / get_kb_answer
# ---------------------------------------------------------------------------


class TestSimpleGetters:
    def test_get_knowledge_base_returns_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(200, {"id": 1, "active": True})
        assert kb_client.get_knowledge_base(1) == {"id": 1, "active": True}

    def test_get_knowledge_base_404_raises(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(
            404, {"error": "not found"}
        )
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.get_knowledge_base(999)
        assert exc.value.status_code == 404

    def test_get_kb_category_returns_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(
            200, {"id": 5, "knowledge_base_id": 1, "child_ids": [], "answer_ids": [10]}
        )
        result = kb_client.get_kb_category(1, 5)
        assert result["id"] == 5
        assert result["answer_ids"] == [10]

    def test_get_kb_answer_single_request_when_no_translations(
        self, kb_client: ZammadClient
    ) -> None:
        kb_client.api.session.get.return_value = _make_response(
            200, {"id": 7, "assets": {}}
        )
        result = kb_client.get_kb_answer(1, 7)
        assert result["id"] == 7
        assert kb_client.api.session.get.call_count == 1

    def test_get_kb_answer_refetches_with_translation(self, kb_client: ZammadClient) -> None:
        first = _make_response(
            200,
            {
                "id": 7,
                "assets": {
                    "KnowledgeBaseAnswer": {"7": {"id": 7, "translation_ids": [42]}}
                },
            },
        )
        second = _make_response(
            200,
            {
                "id": 7,
                "assets": {
                    "KnowledgeBaseAnswer": {"7": {"id": 7, "translation_ids": [42]}},
                    "KnowledgeBaseAnswerTranslation": {
                        "42": {"id": 42, "title": "Hello", "answer_id": 7}
                    },
                    "KnowledgeBaseAnswerTranslationContent": {
                        "42": {"id": 42, "body": "<p>Hi</p>"}
                    },
                },
            },
        )
        kb_client.api.session.get.side_effect = [first, second]
        result = kb_client.get_kb_answer(1, 7)
        assert "KnowledgeBaseAnswerTranslationContent" in result["assets"]
        assert kb_client.api.session.get.call_count == 2


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


class TestExtraction:
    def test_extract_title_and_body(self, kb_client: ZammadClient) -> None:
        payload = {
            "assets": {
                "KnowledgeBaseAnswer": {"7": {"id": 7, "translation_ids": [42]}},
                "KnowledgeBaseAnswerTranslation": {
                    "42": {"id": 42, "title": "Hello", "answer_id": 7}
                },
                "KnowledgeBaseAnswerTranslationContent": {
                    "42": {"id": 42, "body": "<p>Hi <b>there</b>&amp;you</p>"}
                },
            }
        }
        info = kb_client.get_kb_answer_with_content.__wrapped__ if hasattr(
            kb_client.get_kb_answer_with_content, "__wrapped__"
        ) else None
        del info  # not used; we exercise extractors directly below
        answer = kb_client._extract_kb_answer_from_payload(payload, 7)
        assert answer is not None
        assert kb_client._extract_kb_answer_title(payload, answer) == "Hello"
        assert "Hi" in kb_client._extract_kb_answer_body(payload, answer)

    def test_strip_html(self, kb_client: ZammadClient) -> None:
        assert "Hi" in kb_client._strip_html("<p>Hi <b>there</b></p>")
        assert "<" not in kb_client._strip_html("<p>Hi</p>")

    def test_extract_from_flat_payload(self, kb_client: ZammadClient) -> None:
        # Flat dict (no assets) is returned as-is.
        flat = {"id": 7}
        assert kb_client._extract_kb_answer_from_payload(flat, 7) == flat


# ---------------------------------------------------------------------------
# list_kb_answers / search_kb_answers
# ---------------------------------------------------------------------------


def _category_response(answer_ids: list[int], child_ids: list[int] | None = None) -> MagicMock:
    return _make_response(
        200,
        {
            "id": 5,
            "knowledge_base_id": 1,
            "answer_ids": answer_ids,
            "child_ids": child_ids or [],
        },
    )


def _answer_response(answer_id: int, title: str, body: str) -> MagicMock:
    payload = {
        "id": answer_id,
        "assets": {
            "KnowledgeBaseAnswer": {
                str(answer_id): {
                    "id": answer_id,
                    "category_id": 5,
                    "translation_ids": [answer_id * 10],
                }
            },
            "KnowledgeBaseAnswerTranslation": {
                str(answer_id * 10): {
                    "id": answer_id * 10,
                    "title": title,
                    "answer_id": answer_id,
                }
            },
            "KnowledgeBaseAnswerTranslationContent": {
                str(answer_id * 10): {"id": answer_id * 10, "body": body}
            },
        },
    }
    return _make_response(200, payload)


class TestListAndSearch:
    def test_list_kb_answers_injects_title_and_body(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.side_effect = [
            _category_response([1]),
            _answer_response(1, "T1", "<p>Body1</p>"),
            _answer_response(1, "T1", "<p>Body1</p>"),  # second fetch with translation
        ]
        result = kb_client.list_kb_answers(1, 5)
        assert len(result) == 1
        assert result[0]["_title"] == "T1"
        assert "Body1" in result[0]["_body"]

    def test_list_kb_answers_tolerates_per_answer_404(
        self, kb_client: ZammadClient
    ) -> None:
        kb_client.api.session.get.side_effect = [
            _category_response([1, 2]),
            _make_response(404, {"error": "gone"}),  # answer 1 missing
            _answer_response(2, "T2", "<p>B</p>"),
            _answer_response(2, "T2", "<p>B</p>"),
        ]
        result = kb_client.list_kb_answers(1, 5)
        assert len(result) == 1
        assert result[0]["id"] == 2

    def test_list_kb_answers_propagates_non_404(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.side_effect = [
            _category_response([1]),
            _make_response(401, {"error": "auth"}),
        ]
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.list_kb_answers(1, 5)
        assert exc.value.status_code == 401

    def test_search_kb_answers_finds_match_by_title(
        self, kb_client: ZammadClient
    ) -> None:
        kb_client.api.session.get.side_effect = [
            _make_response(
                200, {"id": 1, "category_ids": [5], "answer_ids": []}
            ),  # get_knowledge_base
            _category_response([1]),  # _expand_category_ids fetch of cat 5
            _category_response([1]),  # list_kb_answers fetch of cat 5
            _answer_response(1, "FooBar", "<p>nothing</p>"),
            _answer_response(1, "FooBar", "<p>nothing</p>"),
        ]
        result = kb_client.search_kb_answers(1, "foo")
        assert len(result) == 1
        assert result[0]["_title"] == "FooBar"
        assert result[0]["_category_id"] == 5


# ---------------------------------------------------------------------------
# Server formatters + tool failure semantics
# ---------------------------------------------------------------------------


class TestFormatters:
    def test_format_kb_markdown(self) -> None:
        out = _format_kb_markdown({"id": 1, "active": True, "category_ids": [10]})
        assert "Knowledge Base (ID: 1)" in out
        assert "Root Categories" in out

    def test_format_kb_category_markdown(self) -> None:
        out = _format_kb_category_markdown(
            {"id": 5, "knowledge_base_id": 1, "child_ids": [6], "answer_ids": [7]}
        )
        assert "KB Category (ID: 5)" in out

    def test_format_kb_answer_markdown_status_archived(self) -> None:
        out = _format_kb_answer_markdown(
            {"id": 7, "category_id": 5, "archived_at": "2024-01-01"},
            title="X",
            body="hello",
        )
        assert "archived" in out.lower()
        assert "## Content" in out

    def test_kb_answer_status_levels(self) -> None:
        assert _kb_answer_status({"archived_at": "x"}) == "archived"
        assert _kb_answer_status({"published_at": "x"}) == "published"
        assert _kb_answer_status({"internal_at": "x"}) == "internal"
        assert _kb_answer_status({}) == "draft"


class TestToolFailureSemantics:
    """Maintainer requirement: tool failures must be real errors, not strings.

    We exercise the registered tools through the FastMCP get_tool() API and
    assert that ZammadAPIError raised by the client is propagated rather than
    captured into a successful string payload.
    """

    @pytest.mark.asyncio
    async def test_list_knowledge_bases_propagates_zammad_api_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mcp_zammad import server as srv

        # Build a server with a stubbed client.
        instance = srv.ZammadMCPServer()
        fake_client = MagicMock()
        fake_client.list_knowledge_bases.side_effect = ZammadAPIError(
            500, "https://zammad.example/api/v1/knowledge_bases", {"error": "boom"}
        )
        monkeypatch.setattr(instance, "get_client", lambda: fake_client)

        tool = await instance.mcp.get_tool("zammad_list_knowledge_bases")
        with pytest.raises(ZammadAPIError):
            await tool.run({"params": {}})

    @pytest.mark.asyncio
    async def test_get_kb_answer_propagates_zammad_api_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mcp_zammad import server as srv

        instance = srv.ZammadMCPServer()
        fake_client = MagicMock()
        fake_client.get_kb_answer_with_content.side_effect = ZammadAPIError(
            404, "https://zammad.example/api/v1/knowledge_bases/1/answers/9", {"error": "nope"}
        )
        monkeypatch.setattr(instance, "get_client", lambda: fake_client)

        tool = await instance.mcp.get_tool("zammad_get_kb_answer")
        with pytest.raises(ZammadAPIError):
            await tool.run({"params": {"kb_id": 1, "answer_id": 9}})
