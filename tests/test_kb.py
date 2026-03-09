"""Tests for Knowledge Base client methods and server tools."""

import base64
import json
from collections.abc import Generator
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from mcp_zammad.client import ZammadClient
from mcp_zammad.models import (
    CreateKBAnswerParams,
    CreateKBCategoryParams,
    DeleteKBAnswerParams,
    DeleteKBCategoryParams,
    GetKBAnswerParams,
    GetKBCategoryParams,
    GetKnowledgeBaseParams,
    KBAnswerAttachmentAddParams,
    KBAnswerAttachmentDeleteParams,
    KBAnswerPublishParams,
    KnowledgeBase,
    KnowledgeBaseAnswer,
    KnowledgeBaseCategory,
    ListKBAnswersParams,
    ListKnowledgeBasesParams,
    ResponseFormat,
    UpdateKBAnswerParams,
    UpdateKBCategoryParams,
)
from mcp_zammad.server import (
    ZammadMCPServer,
    _format_kb_answer_markdown,
    _format_kb_category_markdown,
    _format_kb_markdown,
    _kb_answer_status,
)

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

KB_BASE_URL = "https://test.zammad.com/api/v1/"


def _make_mock_response(json_data: object, status_code: int = 200) -> Mock:
    """Build a mock requests.Response."""
    response = Mock()
    response.status_code = status_code
    response.content = b"data"
    response.json.return_value = json_data
    response.raise_for_status = Mock()
    return response


def _make_client(mock_api: Mock) -> ZammadClient:
    """Return a ZammadClient backed by a mock ZammadAPI."""
    client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")
    # The mock_api fixture replaces ZammadAPI at class-creation time, so
    # self.api is the mock instance returned by mock_api().
    return client


# ---------------------------------------------------------------------------
# Client method tests
# ---------------------------------------------------------------------------


class TestKBClientMethods:
    """Unit tests for ZammadClient Knowledge Base methods."""

    @pytest.fixture
    def mock_zammad_api(self) -> Generator[Mock, None, None]:
        with patch("mcp_zammad.client.ZammadAPI") as mock_api:
            yield mock_api

    # --- URL builder ---

    def test_kb_url_simple(self, mock_zammad_api: Mock) -> None:
        """_kb_url builds correct path."""
        mock_zammad_api.return_value.url = KB_BASE_URL
        client = _make_client(mock_zammad_api)
        assert client._kb_url(1) == f"{KB_BASE_URL}knowledge_bases/1"

    def test_kb_url_nested(self, mock_zammad_api: Mock) -> None:
        """_kb_url handles multiple segments."""
        mock_zammad_api.return_value.url = KB_BASE_URL
        client = _make_client(mock_zammad_api)
        assert client._kb_url(1, "answers", 42) == f"{KB_BASE_URL}knowledge_bases/1/answers/42"

    # --- _kb_raise_or_return ---

    def test_kb_raise_or_return_success(self, mock_zammad_api: Mock) -> None:
        """Returns JSON dict on success."""
        mock_zammad_api.return_value.url = KB_BASE_URL
        client = _make_client(mock_zammad_api)
        response = _make_mock_response({"id": 1})
        result = client._kb_raise_or_return(response)
        assert result == {"id": 1}

    def test_kb_raise_or_return_no_content(self, mock_zammad_api: Mock) -> None:
        """Returns empty dict when response has no body."""
        mock_zammad_api.return_value.url = KB_BASE_URL
        client = _make_client(mock_zammad_api)
        response = Mock()
        response.ok = True
        response.status_code = 204
        response.content = b""
        result = client._kb_raise_or_return(response)
        assert result == {}

    def test_kb_raise_or_return_raises_on_error(self, mock_zammad_api: Mock) -> None:
        """Non-ok responses raise Exception with status code and Zammad body."""
        mock_zammad_api.return_value.url = KB_BASE_URL
        client = _make_client(mock_zammad_api)
        response = Mock()
        response.ok = False
        response.status_code = 404
        response.url = "https://example.com/api/v1/knowledge_bases/1/answers/99"
        response.json.return_value = {"error": "Not Found"}
        with pytest.raises(Exception, match="HTTP 404"):
            client._kb_raise_or_return(response)

    # --- list_knowledge_bases ---

    def test_list_knowledge_bases_returns_list(self, mock_zammad_api: Mock) -> None:
        """list_knowledge_bases returns a list when endpoint responds with a list."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        mock_instance.session.get.return_value = _make_mock_response([{"id": 1}, {"id": 2}])
        client = _make_client(mock_zammad_api)
        result = client.list_knowledge_bases()
        assert isinstance(result, list)
        assert len(result) == 2
        mock_instance.session.get.assert_called_once_with(f"{KB_BASE_URL}knowledge_bases")

    def test_list_knowledge_bases_wraps_single_dict(self, mock_zammad_api: Mock) -> None:
        """list_knowledge_bases wraps a bare dict in a list."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        mock_instance.session.get.return_value = _make_mock_response({"id": 1})
        client = _make_client(mock_zammad_api)
        result = client.list_knowledge_bases()
        assert result == [{"id": 1}]

    def test_list_knowledge_bases_fallback_on_404(self, mock_zammad_api: Mock) -> None:
        """list_knowledge_bases falls back to probing IDs when list endpoint returns 404."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        not_found = Mock()
        not_found.status_code = 404
        not_found.content = b"not found"
        kb1_response = _make_mock_response({"id": 1, "active": True})
        # First call: list endpoint → 404; second call: id=1 → 200; third call: id=2 → 404 (stop)
        mock_instance.session.get.side_effect = [not_found, kb1_response, not_found]
        client = _make_client(mock_zammad_api)
        result = client.list_knowledge_bases()
        assert len(result) == 1
        assert result[0]["id"] == 1

    # --- get_knowledge_base ---

    def test_get_knowledge_base(self, mock_zammad_api: Mock) -> None:
        """get_knowledge_base calls correct URL and returns dict."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        kb_data = {"id": 1, "active": True, "category_ids": [10, 11]}
        mock_instance.session.get.return_value = _make_mock_response(kb_data)
        client = _make_client(mock_zammad_api)
        result = client.get_knowledge_base(1)
        assert result["id"] == 1
        mock_instance.session.get.assert_called_once_with(f"{KB_BASE_URL}knowledge_bases/1")

    # --- get_kb_category ---

    def test_get_kb_category(self, mock_zammad_api: Mock) -> None:
        """get_kb_category calls correct URL."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        category_data = {"id": 10, "knowledge_base_id": 1, "answer_ids": [100, 101]}
        mock_instance.session.get.return_value = _make_mock_response(category_data)
        client = _make_client(mock_zammad_api)
        result = client.get_kb_category(1, 10)
        assert result["id"] == 10
        mock_instance.session.get.assert_called_once_with(
            f"{KB_BASE_URL}knowledge_bases/1/categories/10"
        )

    # --- create_kb_category ---

    def test_create_kb_category_minimal(self, mock_zammad_api: Mock) -> None:
        """create_kb_category sends correct payload."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        created = {"id": 20, "knowledge_base_id": 1}
        mock_instance.session.post.return_value = _make_mock_response(created)
        client = _make_client(mock_zammad_api)
        result = client.create_kb_category(kb_id=1, title="Test Cat", kb_locale_id=5)
        assert result["id"] == 20
        call_kwargs = mock_instance.session.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["translations_attributes"][0]["title"] == "Test Cat"
        assert payload["translations_attributes"][0]["kb_locale_id"] == 5
        assert "parent_id" not in payload

    def test_create_kb_category_with_parent(self, mock_zammad_api: Mock) -> None:
        """create_kb_category includes parent_id when provided."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        mock_instance.session.post.return_value = _make_mock_response({"id": 21})
        client = _make_client(mock_zammad_api)
        client.create_kb_category(kb_id=1, title="Child", kb_locale_id=5, parent_id=10)
        payload = mock_instance.session.post.call_args.kwargs["json"]
        assert payload["parent_id"] == 10

    # --- update_kb_category ---

    def test_update_kb_category(self, mock_zammad_api: Mock) -> None:
        """update_kb_category uses PATCH and includes translation."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        mock_instance.session.patch.return_value = _make_mock_response({"id": 10})
        client = _make_client(mock_zammad_api)
        result = client.update_kb_category(
            kb_id=1, category_id=10, title="New Title", translation_id=99
        )
        assert result["id"] == 10
        payload = mock_instance.session.patch.call_args.kwargs["json"]
        assert payload["translations_attributes"][0]["title"] == "New Title"
        assert payload["translations_attributes"][0]["id"] == 99

    def test_update_kb_category_icon_only(self, mock_zammad_api: Mock) -> None:
        """update_kb_category can update just the icon."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        mock_instance.session.patch.return_value = _make_mock_response({"id": 10})
        client = _make_client(mock_zammad_api)
        client.update_kb_category(kb_id=1, category_id=10, category_icon="f115")
        payload = mock_instance.session.patch.call_args.kwargs["json"]
        assert payload["category_icon"] == "f115"
        assert "translations_attributes" not in payload

    # --- delete_kb_category ---

    def test_delete_kb_category(self, mock_zammad_api: Mock) -> None:
        """delete_kb_category calls DELETE on correct URL."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        mock_instance.session.delete.return_value = _make_mock_response({}, status_code=204)
        mock_instance.session.delete.return_value.content = b""
        mock_instance.session.delete.return_value.status_code = 204
        client = _make_client(mock_zammad_api)
        client.delete_kb_category(1, 10)
        mock_instance.session.delete.assert_called_once_with(
            f"{KB_BASE_URL}knowledge_bases/1/categories/10"
        )

    # --- get_kb_answer ---

    def test_get_kb_answer(self, mock_zammad_api: Mock) -> None:
        """get_kb_answer calls correct URL."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        answer_data = {"id": 100, "category_id": 10}
        mock_instance.session.get.return_value = _make_mock_response(answer_data)
        client = _make_client(mock_zammad_api)
        result = client.get_kb_answer(1, 100)
        assert result["id"] == 100
        mock_instance.session.get.assert_called_once_with(
            f"{KB_BASE_URL}knowledge_bases/1/answers/100"
        )

    # --- _extract_kb_answer_from_payload ---

    def test_extract_flat_payload(self, mock_zammad_api: Mock) -> None:
        """_extract_kb_answer_from_payload returns flat dict unchanged."""
        mock_zammad_api.return_value.url = KB_BASE_URL
        client = _make_client(mock_zammad_api)
        payload = {"id": 100, "category_id": 10}
        assert client._extract_kb_answer_from_payload(payload, 100) == payload

    def test_extract_real_zammad_payload(self, mock_zammad_api: Mock) -> None:
        """_extract_kb_answer_from_payload handles real Zammad assets structure."""
        mock_zammad_api.return_value.url = KB_BASE_URL
        client = _make_client(mock_zammad_api)
        inner = {"id": 100, "category_id": 10, "published_at": "2024-01-01T00:00:00Z"}
        payload = {"id": 100, "assets": {"KnowledgeBaseAnswer": {"100": inner}}}
        result = client._extract_kb_answer_from_payload(payload, 100)
        assert result == inner
        assert result["published_at"] == "2024-01-01T00:00:00Z"

    def test_extract_compound_payload_by_id(self, mock_zammad_api: Mock) -> None:
        """_extract_kb_answer_from_payload extracts by top-level KnowledgeBaseAnswer key (legacy)."""
        mock_zammad_api.return_value.url = KB_BASE_URL
        client = _make_client(mock_zammad_api)
        payload = {"KnowledgeBaseAnswer": {"100": {"id": 100, "category_id": 10}}}
        result = client._extract_kb_answer_from_payload(payload, 100)
        assert result == {"id": 100, "category_id": 10}

    def test_extract_compound_payload_fallback(self, mock_zammad_api: Mock) -> None:
        """_extract_kb_answer_from_payload falls back to first value if ID key missing."""
        mock_zammad_api.return_value.url = KB_BASE_URL
        client = _make_client(mock_zammad_api)
        payload = {"assets": {"KnowledgeBaseAnswer": {"999": {"id": 999}}}}
        result = client._extract_kb_answer_from_payload(payload, 100)
        assert result == {"id": 999}

    # --- list_kb_answers ---

    def test_list_kb_answers(self, mock_zammad_api: Mock) -> None:
        """list_kb_answers fetches category then each answer using real Zammad payload."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        category_data = {"id": 10, "knowledge_base_id": 1, "answer_ids": [100, 101]}
        # Real Zammad structure: answer data nested under assets.KnowledgeBaseAnswer
        answer_100_payload = {"id": 100, "assets": {"KnowledgeBaseAnswer": {"100": {"id": 100, "category_id": 10, "published_at": "2024-01-01T00:00:00Z"}}}}
        answer_101_payload = {"id": 101, "assets": {"KnowledgeBaseAnswer": {"101": {"id": 101, "category_id": 10, "published_at": None}}}}
        mock_instance.session.get.side_effect = [
            _make_mock_response(category_data),
            _make_mock_response(answer_100_payload),
            _make_mock_response(answer_101_payload),
        ]
        client = _make_client(mock_zammad_api)
        result = client.list_kb_answers(1, 10)
        assert len(result) == 2
        assert result[0]["id"] == 100
        assert result[0]["published_at"] == "2024-01-01T00:00:00Z"
        assert result[1]["id"] == 101

    def test_list_kb_answers_skips_failed(self, mock_zammad_api: Mock) -> None:
        """list_kb_answers skips answers that fail to fetch."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        category_data = {"id": 10, "knowledge_base_id": 1, "answer_ids": [100, 101]}
        answer_100_payload = {"id": 100, "assets": {"KnowledgeBaseAnswer": {"100": {"id": 100, "category_id": 10}}}}
        error_response = Mock()
        error_response.status_code = 404
        error_response.content = b"not found"
        error_response.raise_for_status.side_effect = requests.HTTPError("404")
        mock_instance.session.get.side_effect = [
            _make_mock_response(category_data),
            _make_mock_response(answer_100_payload),
            error_response,
        ]
        client = _make_client(mock_zammad_api)
        result = client.list_kb_answers(1, 10)
        assert len(result) == 1
        assert result[0]["id"] == 100

    # --- create_kb_answer ---

    def test_create_kb_answer(self, mock_zammad_api: Mock) -> None:
        """create_kb_answer sends correct compound payload."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        created = {"id": 200, "category_id": 10}
        mock_instance.session.post.return_value = _make_mock_response(created)
        client = _make_client(mock_zammad_api)
        result = client.create_kb_answer(
            kb_id=1, category_id=10, title="FAQ", body="<p>Answer</p>", kb_locale_id=5
        )
        assert result["id"] == 200
        payload = mock_instance.session.post.call_args.kwargs["json"]
        assert payload["category_id"] == 10
        trans = payload["translations_attributes"][0]
        assert trans["title"] == "FAQ"
        assert trans["kb_locale_id"] == 5
        assert trans["content_attributes"]["body"] == "<p>Answer</p>"

    # --- update_kb_answer ---

    def test_update_kb_answer_title_and_body(self, mock_zammad_api: Mock) -> None:
        """update_kb_answer sends translation_attributes when title/body given."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        mock_instance.session.patch.return_value = _make_mock_response({"id": 100})
        client = _make_client(mock_zammad_api)
        client.update_kb_answer(
            kb_id=1, answer_id=100, title="New Title", translation_id=55, body="New body"
        )
        payload = mock_instance.session.patch.call_args.kwargs["json"]
        trans = payload["translations_attributes"][0]
        assert trans["id"] == 55
        assert trans["title"] == "New Title"
        assert trans["content_attributes"]["body"] == "New body"

    def test_update_kb_answer_move_category(self, mock_zammad_api: Mock) -> None:
        """update_kb_answer can move answer to new category."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        mock_instance.session.patch.return_value = _make_mock_response({"id": 100})
        client = _make_client(mock_zammad_api)
        client.update_kb_answer(kb_id=1, answer_id=100, category_id=20)
        payload = mock_instance.session.patch.call_args.kwargs["json"]
        assert payload["category_id"] == 20
        assert "translations_attributes" not in payload

    # --- delete_kb_answer ---

    def test_delete_kb_answer(self, mock_zammad_api: Mock) -> None:
        """delete_kb_answer calls DELETE on correct URL."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        del_response = Mock()
        del_response.status_code = 204
        del_response.content = b""
        del_response.raise_for_status = Mock()
        mock_instance.session.delete.return_value = del_response
        client = _make_client(mock_zammad_api)
        client.delete_kb_answer(1, 100)
        mock_instance.session.delete.assert_called_once_with(
            f"{KB_BASE_URL}knowledge_bases/1/answers/100"
        )

    # --- publish / internalize / archive / unarchive ---

    @pytest.mark.parametrize(
        "method_name,action",
        [
            ("publish_kb_answer", "publish"),
            ("internalize_kb_answer", "internal"),
            ("archive_kb_answer", "archive"),
            ("unarchive_kb_answer", "unarchive"),
        ],
    )
    def test_answer_status_transitions(
        self, mock_zammad_api: Mock, method_name: str, action: str
    ) -> None:
        """Status transition methods POST to the correct action endpoint."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        mock_instance.session.post.return_value = _make_mock_response({"id": 100})
        client = _make_client(mock_zammad_api)
        getattr(client, method_name)(1, 100)
        mock_instance.session.post.assert_called_once_with(
            f"{KB_BASE_URL}knowledge_bases/1/answers/100/{action}"
        )

    # --- add_kb_answer_attachment ---

    def test_add_kb_answer_attachment(self, mock_zammad_api: Mock) -> None:
        """add_kb_answer_attachment sends base64 data in payload."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        mock_instance.session.post.return_value = _make_mock_response({"id": 100})
        client = _make_client(mock_zammad_api)
        b64 = base64.b64encode(b"file content").decode()
        client.add_kb_answer_attachment(
            kb_id=1, answer_id=100, filename="test.txt", data=b64, mime_type="text/plain"
        )
        payload = mock_instance.session.post.call_args.kwargs["json"]
        att = payload["attachments"][0]
        assert att["filename"] == "test.txt"
        assert att["data"] == b64
        assert att["mime-type"] == "text/plain"

    # --- delete_kb_answer_attachment ---

    def test_delete_kb_answer_attachment(self, mock_zammad_api: Mock) -> None:
        """delete_kb_answer_attachment calls DELETE on correct URL."""
        mock_instance = mock_zammad_api.return_value
        mock_instance.url = KB_BASE_URL
        del_response = Mock()
        del_response.status_code = 204
        del_response.content = b""
        del_response.raise_for_status = Mock()
        mock_instance.session.delete.return_value = del_response
        client = _make_client(mock_zammad_api)
        client.delete_kb_answer_attachment(1, 100, 999)
        mock_instance.session.delete.assert_called_once_with(
            f"{KB_BASE_URL}knowledge_bases/1/answers/100/attachments/999"
        )


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestKBModels:
    """Unit tests for Knowledge Base Pydantic models."""

    def test_kb_answer_attachment_add_invalid_base64(self) -> None:
        """KBAnswerAttachmentAddParams rejects invalid base64."""
        with pytest.raises(Exception, match="Invalid base64"):
            KBAnswerAttachmentAddParams(
                kb_id=1, answer_id=1, filename="f.txt", data="not!base64!!!", mime_type="text/plain"
            )

    def test_kb_answer_attachment_add_valid_base64(self) -> None:
        """KBAnswerAttachmentAddParams accepts valid base64."""
        b64 = base64.b64encode(b"hello").decode()
        params = KBAnswerAttachmentAddParams(
            kb_id=1, answer_id=1, filename="hello.txt", data=b64, mime_type="text/plain"
        )
        assert params.filename == "hello.txt"

    def test_kb_answer_attachment_add_sanitizes_filename(self) -> None:
        """KBAnswerAttachmentAddParams strips directory traversal from filename."""
        b64 = base64.b64encode(b"x").decode()
        params = KBAnswerAttachmentAddParams(
            kb_id=1, answer_id=1, filename="../../etc/passwd", data=b64, mime_type="text/plain"
        )
        assert "/" not in params.filename
        assert params.filename == "passwd"

    def test_create_kb_category_escapes_html(self) -> None:
        """CreateKBCategoryParams escapes HTML in title."""
        params = CreateKBCategoryParams(
            kb_id=1, title="<script>alert(1)</script>", kb_locale_id=5
        )
        assert "<script>" not in params.title
        assert "&lt;script&gt;" in params.title

    def test_create_kb_answer_escapes_html_in_title(self) -> None:
        """CreateKBAnswerParams escapes HTML in title."""
        params = CreateKBAnswerParams(
            kb_id=1, category_id=10, title="<b>Title</b>", body="body", kb_locale_id=5
        )
        assert "<b>" not in params.title

    def test_kb_category_params_rejects_extra_fields(self) -> None:
        """GetKBCategoryParams rejects extra fields (StrictBaseModel)."""
        with pytest.raises(Exception):
            GetKBCategoryParams(kb_id=1, category_id=5, unknown_field="x")  # type: ignore[call-arg]

    def test_kb_answer_params_rejects_zero_id(self) -> None:
        """GetKBAnswerParams rejects answer_id=0."""
        with pytest.raises(Exception):
            GetKBAnswerParams(kb_id=1, answer_id=0)

    def test_knowledge_base_model_defaults(self) -> None:
        """KnowledgeBase model has sensible defaults."""
        kb = KnowledgeBase(id=1)
        assert kb.active is True
        assert kb.show_feed_icon is False
        assert kb.category_ids is None

    def test_knowledge_base_answer_model(self) -> None:
        """KnowledgeBaseAnswer model parses correctly."""
        answer = KnowledgeBaseAnswer(id=100, category_id=10, promoted=True)
        assert answer.id == 100
        assert answer.promoted is True
        assert answer.attachments is None


# ---------------------------------------------------------------------------
# Formatter helper tests
# ---------------------------------------------------------------------------


class TestKBFormatters:
    """Tests for KB markdown/JSON formatters."""

    def test_kb_answer_status_published(self) -> None:
        assert _kb_answer_status({"published_at": "2024-01-01T00:00:00Z"}) == "published"

    def test_kb_answer_status_internal(self) -> None:
        assert _kb_answer_status({"internal_at": "2024-01-01T00:00:00Z"}) == "internal"

    def test_kb_answer_status_archived(self) -> None:
        assert (
            _kb_answer_status(
                {"archived_at": "2024-01-01T00:00:00Z", "published_at": "2023-01-01T00:00:00Z"}
            )
            == "archived"
        )

    def test_kb_answer_status_draft(self) -> None:
        assert _kb_answer_status({}) == "draft"

    def test_format_kb_markdown_basic(self) -> None:
        kb = {"id": 1, "active": True, "category_ids": [10, 11], "answer_ids": [100]}
        output = _format_kb_markdown(kb)
        assert "Knowledge Base (ID: 1)" in output
        assert "Active" in output

    def test_format_kb_markdown_custom_address(self) -> None:
        kb = {"id": 1, "active": True, "custom_address": "https://kb.example.com"}
        output = _format_kb_markdown(kb)
        assert "https://kb.example.com" in output

    def test_format_kb_category_markdown(self) -> None:
        category = {
            "id": 10,
            "knowledge_base_id": 1,
            "parent_id": None,
            "category_icon": "f115",
            "position": 0,
            "child_ids": [20],
            "answer_ids": [100, 101],
            "translation_ids": [5],
        }
        output = _format_kb_category_markdown(category)
        assert "KB Category (ID: 10)" in output
        assert "f115" in output
        assert "2" in output  # answer count

    def test_format_kb_answer_markdown_with_attachments(self) -> None:
        answer = {
            "id": 100,
            "category_id": 10,
            "published_at": "2024-01-01T00:00:00Z",
            "promoted": True,
            "position": 1,
            "translation_ids": [55],
            "attachments": [{"id": 999, "filename": "doc.pdf", "size": "12345"}],
            "tags": ["faq", "billing"],
        }
        output = _format_kb_answer_markdown(answer)
        assert "KB Answer (ID: 100)" in output
        assert "published" in output
        assert "doc.pdf" in output
        assert "faq" in output

    def test_format_kb_answer_markdown_draft(self) -> None:
        answer = {"id": 200, "category_id": 5, "promoted": False, "position": 0}
        output = _format_kb_answer_markdown(answer)
        assert "draft" in output


# ---------------------------------------------------------------------------
# Server tool tests
# ---------------------------------------------------------------------------


class TestKBServerTools:
    """Integration-style tests for KB MCP tools via server setup."""

    @pytest.fixture
    def server_and_client(self) -> Generator[tuple[ZammadMCPServer, Mock], None, None]:
        """Provide a ZammadMCPServer with a mock ZammadClient."""
        with patch("mcp_zammad.server.ZammadClient"):
            server = ZammadMCPServer()
            mock_client = Mock()
            server.client = mock_client
            yield server, mock_client

    def _get_tool(self, server: ZammadMCPServer, name: str):
        """Extract a registered tool function by name."""
        for tool in server.mcp._tool_manager._tools.values():
            if tool.name == name:
                return tool.fn
        raise KeyError(f"Tool '{name}' not found")

    def test_list_knowledge_bases_markdown(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_list_knowledge_bases returns markdown for MARKDOWN format."""
        server, mock_client = server_and_client
        mock_client.list_knowledge_bases.return_value = [
            {"id": 1, "active": True, "category_ids": [10]}
        ]
        fn = self._get_tool(server, "zammad_list_knowledge_bases")
        result = fn(params=ListKnowledgeBasesParams())
        assert "Knowledge Bases" in result
        assert "KB ID: 1" in result

    def test_list_knowledge_bases_json(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_list_knowledge_bases returns JSON for JSON format."""
        server, mock_client = server_and_client
        mock_client.list_knowledge_bases.return_value = [{"id": 1, "active": True}]
        fn = self._get_tool(server, "zammad_list_knowledge_bases")
        result = fn(params=ListKnowledgeBasesParams(response_format=ResponseFormat.JSON))
        data = json.loads(result)
        assert data["count"] == 1
        assert data["items"][0]["id"] == 1

    def test_list_knowledge_bases_error(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_list_knowledge_bases returns error string on exception."""
        server, mock_client = server_and_client
        mock_client.list_knowledge_bases.side_effect = Exception("connection error")
        fn = self._get_tool(server, "zammad_list_knowledge_bases")
        result = fn(params=ListKnowledgeBasesParams())
        assert "Error" in result

    def test_get_knowledge_base_markdown(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_get_knowledge_base returns markdown."""
        server, mock_client = server_and_client
        mock_client.get_knowledge_base.return_value = {
            "id": 1, "active": True, "category_ids": [], "answer_ids": []
        }
        fn = self._get_tool(server, "zammad_get_knowledge_base")
        result = fn(params=GetKnowledgeBaseParams(kb_id=1))
        assert "Knowledge Base (ID: 1)" in result
        mock_client.get_knowledge_base.assert_called_once_with(1)

    def test_get_knowledge_base_not_found(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_get_knowledge_base handles 404."""
        server, mock_client = server_and_client
        mock_client.get_knowledge_base.side_effect = requests.HTTPError("404 Not Found")
        fn = self._get_tool(server, "zammad_get_knowledge_base")
        result = fn(params=GetKnowledgeBaseParams(kb_id=999))
        assert "not found" in result.lower() or "Error" in result

    def test_get_kb_category_markdown(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_get_kb_category returns markdown."""
        server, mock_client = server_and_client
        mock_client.get_kb_category.return_value = {
            "id": 10, "knowledge_base_id": 1, "answer_ids": [], "child_ids": [], "translation_ids": []
        }
        fn = self._get_tool(server, "zammad_get_kb_category")
        result = fn(params=GetKBCategoryParams(kb_id=1, category_id=10))
        assert "KB Category (ID: 10)" in result

    def test_create_kb_category(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_create_kb_category calls client and returns JSON."""
        server, mock_client = server_and_client
        mock_client.create_kb_category.return_value = {"id": 20, "knowledge_base_id": 1}
        fn = self._get_tool(server, "zammad_create_kb_category")
        result = fn(params=CreateKBCategoryParams(kb_id=1, title="New Cat", kb_locale_id=5))
        data = json.loads(result)
        assert data["id"] == 20
        mock_client.create_kb_category.assert_called_once()

    def test_update_kb_category(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_update_kb_category calls client and returns JSON."""
        server, mock_client = server_and_client
        mock_client.update_kb_category.return_value = {"id": 10}
        fn = self._get_tool(server, "zammad_update_kb_category")
        result = fn(
            params=UpdateKBCategoryParams(kb_id=1, category_id=10, title="Updated", translation_id=99)
        )
        data = json.loads(result)
        assert data["id"] == 10
        mock_client.update_kb_category.assert_called_once_with(
            kb_id=1, category_id=10, title="Updated", translation_id=99,
            parent_id=None, category_icon=None
        )

    def test_delete_kb_category(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_delete_kb_category returns confirmation message."""
        server, mock_client = server_and_client
        mock_client.delete_kb_category.return_value = {}
        fn = self._get_tool(server, "zammad_delete_kb_category")
        result = fn(params=DeleteKBCategoryParams(kb_id=1, category_id=10))
        assert "deleted" in result
        assert "10" in result

    def test_list_kb_answers_markdown(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_list_kb_answers returns markdown."""
        server, mock_client = server_and_client
        mock_client.list_kb_answers.return_value = [
            {"id": 100, "category_id": 10, "published_at": "2024-01-01T00:00:00Z"}
        ]
        fn = self._get_tool(server, "zammad_list_kb_answers")
        result = fn(params=ListKBAnswersParams(kb_id=1, category_id=10))
        assert "Answer ID: 100" in result

    def test_get_kb_answer_markdown(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_get_kb_answer returns formatted answer."""
        server, mock_client = server_and_client
        payload = {"id": 100, "category_id": 10, "published_at": "2024-01-01T00:00:00Z"}
        mock_client.get_kb_answer.return_value = payload
        mock_client._extract_kb_answer_from_payload.return_value = payload
        fn = self._get_tool(server, "zammad_get_kb_answer")
        result = fn(params=GetKBAnswerParams(kb_id=1, answer_id=100))
        assert "KB Answer (ID: 100)" in result

    def test_create_kb_answer(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_create_kb_answer calls client and returns JSON."""
        server, mock_client = server_and_client
        mock_client.create_kb_answer.return_value = {"id": 200, "category_id": 10}
        fn = self._get_tool(server, "zammad_create_kb_answer")
        result = fn(
            params=CreateKBAnswerParams(
                kb_id=1, category_id=10, title="FAQ", body="<p>body</p>", kb_locale_id=5
            )
        )
        data = json.loads(result)
        assert data["id"] == 200

    def test_update_kb_answer(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_update_kb_answer calls client with correct args."""
        server, mock_client = server_and_client
        mock_client.update_kb_answer.return_value = {"id": 100}
        fn = self._get_tool(server, "zammad_update_kb_answer")
        result = fn(
            params=UpdateKBAnswerParams(
                kb_id=1, answer_id=100, title="New Title", translation_id=55
            )
        )
        data = json.loads(result)
        assert data["id"] == 100

    def test_delete_kb_answer(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_delete_kb_answer returns confirmation."""
        server, mock_client = server_and_client
        mock_client.delete_kb_answer.return_value = {}
        fn = self._get_tool(server, "zammad_delete_kb_answer")
        result = fn(params=DeleteKBAnswerParams(kb_id=1, answer_id=100))
        assert "deleted" in result
        assert "100" in result

    @pytest.mark.parametrize(
        "tool_name,client_method",
        [
            ("zammad_publish_kb_answer", "publish_kb_answer"),
            ("zammad_internalize_kb_answer", "internalize_kb_answer"),
            ("zammad_archive_kb_answer", "archive_kb_answer"),
            ("zammad_unarchive_kb_answer", "unarchive_kb_answer"),
        ],
    )
    def test_answer_status_tools(
        self,
        server_and_client: tuple[ZammadMCPServer, Mock],
        tool_name: str,
        client_method: str,
    ) -> None:
        """Status transition tools call correct client method and return JSON."""
        server, mock_client = server_and_client
        getattr(mock_client, client_method).return_value = {"id": 100}
        fn = self._get_tool(server, tool_name)
        result = fn(params=KBAnswerPublishParams(kb_id=1, answer_id=100))
        data = json.loads(result)
        assert data["id"] == 100
        getattr(mock_client, client_method).assert_called_once_with(1, 100)

    def test_add_kb_answer_attachment(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_add_kb_answer_attachment calls client and returns JSON."""
        server, mock_client = server_and_client
        mock_client.add_kb_answer_attachment.return_value = {"id": 100}
        fn = self._get_tool(server, "zammad_add_kb_answer_attachment")
        b64 = base64.b64encode(b"data").decode()
        result = fn(
            params=KBAnswerAttachmentAddParams(
                kb_id=1, answer_id=100, filename="file.pdf", data=b64, mime_type="application/pdf"
            )
        )
        data = json.loads(result)
        assert data["id"] == 100

    def test_delete_kb_answer_attachment(
        self, server_and_client: tuple[ZammadMCPServer, Mock]
    ) -> None:
        """zammad_delete_kb_answer_attachment returns confirmation."""
        server, mock_client = server_and_client
        mock_client.delete_kb_answer_attachment.return_value = {}
        fn = self._get_tool(server, "zammad_delete_kb_answer_attachment")
        result = fn(
            params=KBAnswerAttachmentDeleteParams(kb_id=1, answer_id=100, attachment_id=999)
        )
        assert "999" in result
        assert "deleted" in result
        mock_client.delete_kb_answer_attachment.assert_called_once_with(1, 100, 999)
