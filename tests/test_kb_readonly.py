"""
Tests for the read-only Knowledge Base feature (PR1).

Scope:
- ZammadClient KB read-only methods (mocked HTTP).
- ZammadAPIError typed-error semantics.
- MCP tool error semantics: failures must propagate as exceptions, not as
  successful string payloads.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from mcp_zammad import server as srv
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
    json_body: object | None = None,
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

    def test_204_or_empty_body_raises(self, kb_client: ZammadClient) -> None:
        resp = _make_response(204)
        with pytest.raises(ZammadAPIError) as exc:
            kb_client._kb_raise_or_return(resp)
        assert exc.value.status_code == 204


class TestListKnowledgeBases:
    def test_returns_knowledge_bases_from_init_assets(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.post.return_value = _make_response(
            200,
            {
                "assets": {
                    "KnowledgeBase": {
                        "1": {"id": 1, "active": True},
                        "3": {"id": 3, "active": True},
                    }
                }
            },
        )

        assert kb_client.list_knowledge_bases() == [
            {"id": 1, "active": True},
            {"id": 3, "active": True},
        ]
        kb_client.api.session.post.assert_called_once_with(kb_client.api.url + "knowledge_bases/init")
        kb_client.api.session.get.assert_not_called()

    def test_empty_init_payload_returns_empty_list(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.post.return_value = _make_response(200, {})
        assert kb_client.list_knowledge_bases() == []

    @pytest.mark.parametrize("status_code", [401, 500])
    def test_http_error_raises_typed_error(self, kb_client: ZammadClient, status_code: int) -> None:
        kb_client.api.session.post.return_value = _make_response(status_code, {"error": "failed"})
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.list_knowledge_bases()
        assert exc.value.status_code == status_code

    def test_empty_body_raises_typed_error(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.post.return_value = _make_response(200)
        with pytest.raises(ZammadAPIError):
            kb_client.list_knowledge_bases()

    def test_unexpected_shape_raises_typed_error(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.post.return_value = _make_response(200, "weird")
        with pytest.raises(ZammadAPIError):
            kb_client.list_knowledge_bases()


class TestSimpleGetters:
    def test_get_knowledge_base_returns_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(200, {"id": 1, "active": True})
        assert kb_client.get_knowledge_base(1) == {"id": 1, "active": True}

    def test_get_knowledge_base_404_raises(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(404, {"error": "not found"})
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.get_knowledge_base(999)
        assert exc.value.status_code == 404

    def test_get_knowledge_base_rejects_null_body(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(200, None, content=b"null")
        with pytest.raises(ZammadAPIError):
            kb_client.get_knowledge_base(1)

    def test_get_knowledge_base_wraps_invalid_json(self, kb_client: ZammadClient) -> None:
        response = _make_response(200, content=b"not-json")
        response.json.side_effect = ValueError("invalid json")
        response.text = "not-json"
        kb_client.api.session.get.return_value = response
        with pytest.raises(ZammadAPIError):
            kb_client.get_knowledge_base(1)

    def test_get_kb_category_returns_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(
            200, {"id": 5, "knowledge_base_id": 1, "child_ids": [], "answer_ids": [10]}
        )
        result = kb_client.get_kb_category(1, 5)
        assert result["id"] == 5
        assert result["answer_ids"] == [10]

    def test_get_kb_answer_single_request_when_no_translations(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(200, {"id": 7, "assets": {}})
        result = kb_client.get_kb_answer(1, 7)
        assert result["id"] == 7
        assert kb_client.api.session.get.call_count == 1

    def test_get_kb_answer_refetches_with_translation(self, kb_client: ZammadClient) -> None:
        first = _make_response(
            200,
            {
                "id": 7,
                "assets": {"KnowledgeBaseAnswer": {"7": {"id": 7, "translation_ids": [42]}}},
            },
        )
        second = _make_response(
            200,
            {
                "id": 7,
                "assets": {
                    "KnowledgeBaseAnswer": {"7": {"id": 7, "translation_ids": [42]}},
                    "KnowledgeBaseAnswerTranslation": {"42": {"id": 42, "title": "Hello", "answer_id": 7}},
                    "KnowledgeBaseAnswerTranslationContent": {"42": {"id": 42, "body": "<p>Hi</p>"}},
                },
            },
        )
        kb_client.api.session.get.side_effect = [first, second]
        result = kb_client.get_kb_answer(1, 7)
        assert "KnowledgeBaseAnswerTranslationContent" in result["assets"]
        assert kb_client.api.session.get.call_count == 2


class TestExtraction:
    def test_extract_title_and_body(self, kb_client: ZammadClient) -> None:
        payload = {
            "assets": {
                "KnowledgeBaseAnswer": {"7": {"id": 7, "translation_ids": [42]}},
                "KnowledgeBaseAnswerTranslation": {"42": {"id": 42, "title": "Hello", "answer_id": 7}},
                "KnowledgeBaseAnswerTranslationContent": {"42": {"id": 42, "body": "<p>Hi <b>there</b>&amp;you</p>"}},
            }
        }
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
            "KnowledgeBaseAnswerTranslationContent": {str(answer_id * 10): {"id": answer_id * 10, "body": body}},
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

    def test_list_kb_answers_tolerates_per_answer_404(self, kb_client: ZammadClient) -> None:
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

    def test_search_kb_answers_finds_match_by_title(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.side_effect = [
            _make_response(200, {"id": 1, "category_ids": [5], "answer_ids": []}),  # get_knowledge_base
            _category_response([1]),  # _expand_category_ids fetch of cat 5
            _category_response([1]),  # list_kb_answers fetch of cat 5
            _answer_response(1, "FooBar", "<p>nothing</p>"),
            _answer_response(1, "FooBar", "<p>nothing</p>"),
        ]
        result = kb_client.search_kb_answers(1, "foo")
        assert len(result) == 1
        assert result[0]["_title"] == "FooBar"
        assert result[0]["_category_id"] == 5


class TestFormatters:
    def test_format_kb_markdown(self) -> None:
        out = _format_kb_markdown({"id": 1, "active": True, "category_ids": [10]})
        assert "Knowledge Base (ID: 1)" in out
        assert "Root Categories" in out

    def test_format_kb_category_markdown(self) -> None:
        out = _format_kb_category_markdown({"id": 5, "knowledge_base_id": 1, "child_ids": [6], "answer_ids": [7]})
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


class TestKBToolSuccessSemantics:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("tool_name", "params", "client_method", "client_result"),
        [
            (
                "zammad_list_knowledge_bases",
                {},
                "list_knowledge_bases",
                [{"id": 1, "active": True}],
            ),
            (
                "zammad_get_knowledge_base",
                {"kb_id": 1},
                "get_knowledge_base",
                {"id": 1, "active": True},
            ),
            (
                "zammad_get_kb_category",
                {"kb_id": 1, "category_id": 2},
                "get_kb_category",
                {"id": 2, "knowledge_base_id": 1},
            ),
            (
                "zammad_list_kb_answers",
                {"kb_id": 1, "category_id": 2},
                "list_kb_answers",
                [{"id": 3, "_title": "Example"}],
            ),
            (
                "zammad_search_kb_answers",
                {"kb_id": 1, "query": "example"},
                "search_kb_answers",
                [{"id": 3, "_title": "Example", "_category_id": 2}],
            ),
            (
                "zammad_get_kb_answer",
                {"kb_id": 1, "answer_id": 3},
                "get_kb_answer_with_content",
                {"answer": {"id": 3, "category_id": 2}, "title": "Example", "body": "Body"},
            ),
        ],
    )
    async def test_json_tools_return_successful_results(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tool_name: str,
        params: dict[str, object],
        client_method: str,
        client_result: object,
    ) -> None:
        instance = srv.ZammadMCPServer()
        fake_client = MagicMock()
        getattr(fake_client, client_method).return_value = client_result
        monkeypatch.setattr(instance, "get_client", lambda: fake_client)
        tool = await instance.mcp.get_tool(tool_name)

        result = await tool.run({"params": {**params, "response_format": "json"}})

        assert result.content
        assert json.loads(result.content[0].text)

    @pytest.mark.asyncio
    async def test_list_tool_returns_markdown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        instance = srv.ZammadMCPServer()
        fake_client = MagicMock()
        fake_client.list_knowledge_bases.return_value = [
            {"id": 1, "active": True, "custom_address": "support.example", "category_ids": [2]}
        ]
        monkeypatch.setattr(instance, "get_client", lambda: fake_client)
        tool = await instance.mcp.get_tool("zammad_list_knowledge_bases")

        result = await tool.run({"params": {}})

        assert "# Knowledge Bases" in result.content[0].text
        assert "support.example" in result.content[0].text


class TestToolFailureSemantics:
    """
    Maintainer requirement: tool failures must be real errors, not strings.

    We exercise the registered tools through the FastMCP get_tool() API and
    assert that ZammadAPIError raised by the client is propagated rather than
    captured into a successful string payload.
    """

    @pytest.mark.asyncio
    async def test_list_knowledge_bases_propagates_zammad_api_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
    async def test_get_kb_answer_propagates_zammad_api_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        instance = srv.ZammadMCPServer()
        fake_client = MagicMock()
        fake_client.get_kb_answer_with_content.side_effect = ZammadAPIError(
            404, "https://zammad.example/api/v1/knowledge_bases/1/answers/9", {"error": "nope"}
        )
        monkeypatch.setattr(instance, "get_client", lambda: fake_client)

        tool = await instance.mcp.get_tool("zammad_get_kb_answer")
        with pytest.raises(ZammadAPIError):
            await tool.run({"params": {"kb_id": 1, "answer_id": 9}})


class TestKBToolMarkdownOutputs:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("tool_name", "params", "client_method", "client_result", "expected"),
        [
            (
                "zammad_list_knowledge_bases",
                {},
                "list_knowledge_bases",
                [{"id": 1, "active": True, "custom_address": "support.example", "category_ids": [2]}],
                "# Knowledge Bases",
            ),
            (
                "zammad_get_knowledge_base",
                {"kb_id": 1},
                "get_knowledge_base",
                {"id": 1, "active": True, "category_ids": [2], "answer_ids": [3]},
                "# Knowledge Base (ID: 1)",
            ),
            (
                "zammad_get_kb_category",
                {"kb_id": 1, "category_id": 2},
                "get_kb_category",
                {"id": 2, "knowledge_base_id": 1, "child_ids": [3], "answer_ids": [4]},
                "# KB Category (ID: 2)",
            ),
            (
                "zammad_list_kb_answers",
                {"kb_id": 1, "category_id": 2},
                "list_kb_answers",
                [{"id": 3, "_title": "Example", "promoted": True, "position": 1}],
                "# KB Answers in Category 2 (KB: 1)",
            ),
            (
                "zammad_search_kb_answers",
                {"kb_id": 1, "query": "example"},
                "search_kb_answers",
                [{"id": 3, "_title": "Example", "_category_id": 2}],
                "KB Answer Search: 'example'",
            ),
            (
                "zammad_get_kb_answer",
                {"kb_id": 1, "answer_id": 3},
                "get_kb_answer_with_content",
                {"answer": {"id": 3, "category_id": 2}, "title": "Example", "body": "Body text"},
                "# Example",
            ),
        ],
    )
    async def test_tool_returns_markdown(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tool_name: str,
        params: dict[str, object],
        client_method: str,
        client_result: object,
        expected: str,
    ) -> None:
        instance = srv.ZammadMCPServer()
        fake_client = MagicMock()
        getattr(fake_client, client_method).return_value = client_result
        monkeypatch.setattr(instance, "get_client", lambda: fake_client)
        tool = await instance.mcp.get_tool(tool_name)

        result = await tool.run({"params": params})

        assert expected in result.content[0].text

    @pytest.mark.asyncio
    async def test_search_no_results_returns_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        instance = srv.ZammadMCPServer()
        fake_client = MagicMock()
        fake_client.search_kb_answers.return_value = []
        monkeypatch.setattr(instance, "get_client", lambda: fake_client)
        tool = await instance.mcp.get_tool("zammad_search_kb_answers")

        result = await tool.run({"params": {"kb_id": 1, "query": "nope"}})

        assert "No KB answers found matching 'nope'" in result.content[0].text


class TestKBClientShapeErrors:
    def test_list_init_payload_not_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.post.return_value = _make_response(200, [1, 2, 3])
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.list_knowledge_bases()
        assert "init response shape" in str(exc.value.body).lower()

    def test_list_assets_not_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.post.return_value = _make_response(200, {"assets": [1, 2]})
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.list_knowledge_bases()
        assert "assets shape" in str(exc.value.body).lower()

    def test_list_knowledge_bases_not_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.post.return_value = _make_response(200, {"assets": {"KnowledgeBase": []}})
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.list_knowledge_bases()
        assert "knowledgebase assets shape" in str(exc.value.body).lower()

    def test_list_single_kb_not_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.post.return_value = _make_response(200, {"assets": {"KnowledgeBase": {"1": "bad"}}})
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.list_knowledge_bases()
        assert "knowledgebase asset shape" in str(exc.value.body).lower()

    def test_get_knowledge_base_not_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(200, [1])
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.get_knowledge_base(1)
        assert "knowledge_base response shape" in str(exc.value.body).lower()

    def test_get_kb_category_not_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(200, [1])
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.get_kb_category(1, 2)
        assert "kb_category response shape" in str(exc.value.body).lower()

    def test_get_kb_answer_not_dict(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(200, [1])
        with pytest.raises(ZammadAPIError) as exc:
            kb_client.get_kb_answer(1, 2)
        assert "kb_answer response shape" in str(exc.value.body).lower()


class TestKBExtractionFallbacks:
    def test_title_falls_back_to_first_translation(self, kb_client: ZammadClient) -> None:
        payload = {
            "assets": {
                "KnowledgeBaseAnswer": {"7": {"id": 7, "translation_ids": [99]}},
                "KnowledgeBaseAnswerTranslation": {
                    "42": {"id": 42, "title": "Fallback", "answer_id": 7},
                },
            }
        }
        answer = kb_client._extract_kb_answer_from_payload(payload, 7)
        assert kb_client._extract_kb_answer_title(payload, answer) == "Fallback"

    def test_body_falls_back_to_legacy_translation_content(self, kb_client: ZammadClient) -> None:
        payload = {
            "assets": {
                "KnowledgeBaseAnswer": {"7": {"id": 7, "translation_ids": [42]}},
                "KnowledgeBaseAnswerTranslation": {
                    "42": {
                        "id": 42,
                        "title": "Hello",
                        "answer_id": 7,
                        "content_attributes": {"body": "<p>Legacy</p>"},
                    }
                },
            }
        }
        answer = kb_client._extract_kb_answer_from_payload(payload, 7)
        assert "Legacy" in kb_client._extract_kb_answer_body(payload, answer)

    def test_extract_answer_from_flat_payload(self, kb_client: ZammadClient) -> None:
        flat = {"KnowledgeBaseAnswer": {"7": {"id": 7}}}
        answer = kb_client._extract_kb_answer_from_payload(flat, 7)
        assert answer == {"id": 7}

    def test_extract_answer_returns_none_when_missing(self, kb_client: ZammadClient) -> None:
        assert kb_client._extract_kb_answer_from_payload({}, 7) is None


class TestKBBFSErrorPropagation:
    def test_expand_category_raises_non_404(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(500, {"error": "boom"})
        with pytest.raises(ZammadAPIError) as exc:
            kb_client._expand_category_ids(1, [2])
        assert exc.value.status_code == 500

    def test_collect_category_answers_raises_non_404(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(500, {"error": "boom"})
        with pytest.raises(ZammadAPIError) as exc:
            kb_client._collect_category_answers(1, 2, "test")
        assert exc.value.status_code == 500


class TestKBResources:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("uri", "client_method", "client_args", "client_result", "expected"),
        [
            (
                "zammad://kb/1",
                "get_knowledge_base",
                (1,),
                {"id": 1, "active": True, "category_ids": [2], "answer_ids": []},
                "# Knowledge Base (ID: 1)",
            ),
            (
                "zammad://kb/1/category/2",
                "get_kb_category",
                (1, 2),
                {"id": 2, "knowledge_base_id": 1, "child_ids": [], "answer_ids": [3]},
                "# KB Category (ID: 2)",
            ),
            (
                "zammad://kb/1/answer/3",
                "get_kb_answer_with_content",
                (1, 3),
                {"answer": {"id": 3, "category_id": 2}, "title": "Resource", "body": "Body"},
                "# Resource",
            ),
        ],
    )
    async def test_kb_resources_return_markdown(
        self,
        monkeypatch: pytest.MonkeyPatch,
        uri: str,
        client_method: str,
        client_args: tuple[object, ...],
        client_result: object,
        expected: str,
    ) -> None:
        instance = srv.ZammadMCPServer()
        fake_client = MagicMock()
        getattr(fake_client, client_method).return_value = client_result
        monkeypatch.setattr(instance, "get_client", lambda: fake_client)

        result = await instance.mcp.read_resource(uri)

        assert any(expected in c.content for c in result.contents)


class TestKBCoverageEdgeCases:
    def test_get_kb_answer_with_content(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.return_value = _make_response(
            200,
            {
                "id": 7,
                "assets": {
                    "KnowledgeBaseAnswer": {"7": {"id": 7, "translation_ids": [42]}},
                    "KnowledgeBaseAnswerTranslation": {"42": {"id": 42, "title": "Title", "answer_id": 7}},
                },
            },
        )
        result = kb_client.get_kb_answer_with_content(1, 7)
        assert result["answer"]["id"] == 7
        assert result["title"] == "Title"

    def test_extract_title_empty_when_no_translations(self, kb_client: ZammadClient) -> None:
        payload = {"assets": {"KnowledgeBaseAnswer": {"7": {"id": 7, "translation_ids": [42]}}}}
        answer = kb_client._extract_kb_answer_from_payload(payload, 7)
        assert kb_client._extract_kb_answer_title(payload, answer) == ""

    def test_list_kb_answers_skips_empty_answer_payload(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.side_effect = [
            _make_response(200, {"id": 2, "knowledge_base_id": 1, "answer_ids": [7]}),
            _make_response(200, {}),  # answer 7 parses to None
        ]
        answers = kb_client.list_kb_answers(1, 2)
        assert answers == []

    def test_expand_category_ids_with_children_and_404(self, kb_client: ZammadClient) -> None:
        kb_client.api.session.get.side_effect = [
            _make_response(200, {"id": 2, "knowledge_base_id": 1, "child_ids": [3], "answer_ids": []}),
            _make_response(200, {"id": 3, "knowledge_base_id": 1, "child_ids": [4], "answer_ids": []}),
            _make_response(404, {"error": "not found"}),  # category 4 missing
        ]
        ids = kb_client._expand_category_ids(1, [2])
        assert ids == [2, 3, 4]
