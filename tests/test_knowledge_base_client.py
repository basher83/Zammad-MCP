"""Tests for read-only knowledge-base methods on ZammadClient.

The Zammad API capability is replaced with a controlled ``ZammadAPI`` double so no
network access or credentials are required.
"""

from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

import pytest
import requests

from mcp_zammad.client import ZammadClient
from mcp_zammad.knowledge_base import KnowledgeBaseNotFoundError, KnowledgeBaseResponseError

KB_ID = 1
ROOT_CATEGORY_ID = 10
CHILD_CATEGORY_ID = 11
ROOT_ANSWER_ID = 100
CHILD_ANSWER_ID = 101
ROOT_CONTENT_ID = 500


def _init_assets() -> dict[str, Any]:
    """Return a ``knowledge_bases/init`` payload shaped like Zammad's asset response."""
    return {
        "KnowledgeBase": {"1": {"id": KB_ID, "active": True}},
        "KnowledgeBaseTranslation": {"1": {"id": 1, "knowledge_base_id": KB_ID, "kb_locale_id": 1, "title": "Help"}},
        "KnowledgeBaseLocale": {"1": {"id": 1, "knowledge_base_id": KB_ID, "primary": True}},
        "KnowledgeBaseCategory": {
            "10": {"id": ROOT_CATEGORY_ID, "knowledge_base_id": KB_ID, "parent_id": None},
            "11": {"id": CHILD_CATEGORY_ID, "knowledge_base_id": KB_ID, "parent_id": ROOT_CATEGORY_ID},
        },
        "KnowledgeBaseCategoryTranslation": {
            "10": {"id": 10, "category_id": ROOT_CATEGORY_ID, "kb_locale_id": 1, "title": "Getting Started"},
            "11": {"id": 11, "category_id": CHILD_CATEGORY_ID, "kb_locale_id": 1, "title": "VPN"},
        },
        "KnowledgeBaseAnswer": {
            "100": {"id": ROOT_ANSWER_ID, "category_id": ROOT_CATEGORY_ID, "published_at": "2024-01-01T00:00:00Z"},
            "101": {"id": CHILD_ANSWER_ID, "category_id": CHILD_CATEGORY_ID, "published_at": None},
        },
        "KnowledgeBaseAnswerTranslation": {
            "100": {
                "id": 100,
                "answer_id": ROOT_ANSWER_ID,
                "kb_locale_id": 1,
                "title": "Reset your password",
                "content_id": ROOT_CONTENT_ID,
            },
            "101": {
                "id": 101,
                "answer_id": CHILD_ANSWER_ID,
                "kb_locale_id": 1,
                "title": "Connect to the VPN",
                "content_id": 501,
            },
        },
    }


@pytest.fixture
def api() -> Generator[Mock, None, None]:
    """Provide a ZammadAPI double whose ``init`` returns a populated knowledge base."""
    with patch("mcp_zammad.client.ZammadAPI") as api_class:
        instance = Mock()
        instance.knowledge_bases.init.return_value = _init_assets()
        api_class.return_value = instance
        yield instance


@pytest.fixture
def client(api: Mock) -> ZammadClient:
    """Provide a client wired to the API double."""
    return ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")


def test_list_knowledge_bases_discovers_via_init(client: ZammadClient, api: Mock) -> None:
    result = client.list_knowledge_bases()

    api.knowledge_bases.init.assert_called_once_with()
    assert result == [
        {
            "id": KB_ID,
            "title": "Help",
            "active": True,
            "root_category_ids": [ROOT_CATEGORY_ID],
            "category_count": 2,
            "answer_count": 2,
        }
    ]


def test_list_knowledge_bases_is_empty_when_nothing_visible(client: ZammadClient, api: Mock) -> None:
    api.knowledge_bases.init.return_value = {}

    assert client.list_knowledge_bases() == []


def test_list_knowledge_bases_propagates_api_errors(client: ZammadClient, api: Mock) -> None:
    api.knowledge_bases.init.side_effect = requests.HTTPError("401 Unauthorized")

    with pytest.raises(requests.HTTPError):
        client.list_knowledge_bases()


def test_list_knowledge_bases_rejects_unexpected_payload(client: ZammadClient, api: Mock) -> None:
    api.knowledge_bases.init.return_value = b"<html>login</html>"

    with pytest.raises(KnowledgeBaseResponseError):
        client.list_knowledge_bases()


def test_get_knowledge_base_unknown_id_raises(client: ZammadClient) -> None:
    with pytest.raises(KnowledgeBaseNotFoundError):
        client.get_knowledge_base(99)


def test_get_kb_category_returns_hierarchy(client: ZammadClient) -> None:
    assert client.get_kb_category(KB_ID, ROOT_CATEGORY_ID) == {
        "id": ROOT_CATEGORY_ID,
        "knowledge_base_id": KB_ID,
        "parent_id": None,
        "title": "Getting Started",
        "child_category_ids": [CHILD_CATEGORY_ID],
        "answer_ids": [ROOT_ANSWER_ID],
    }


def test_get_kb_category_unknown_id_raises(client: ZammadClient) -> None:
    with pytest.raises(KnowledgeBaseNotFoundError):
        client.get_kb_category(KB_ID, 99)


def test_list_kb_answers_filters_by_category(client: ZammadClient) -> None:
    all_ids = [a["id"] for a in client.list_kb_answers(KB_ID)]
    child_ids = [a["id"] for a in client.list_kb_answers(KB_ID, category_id=CHILD_CATEGORY_ID)]

    assert all_ids == [ROOT_ANSWER_ID, CHILD_ANSWER_ID]
    assert child_ids == [CHILD_ANSWER_ID]


def test_list_kb_answers_unknown_category_raises(client: ZammadClient) -> None:
    with pytest.raises(KnowledgeBaseNotFoundError):
        client.list_kb_answers(KB_ID, category_id=99)


def test_search_kb_answers_matches_title_case_insensitively(client: ZammadClient) -> None:
    assert [a["id"] for a in client.search_kb_answers(KB_ID, "PASSWORD")] == [ROOT_ANSWER_ID]
    assert client.search_kb_answers(KB_ID, "printer") == []


def test_get_kb_answer_fetches_body_for_translation_content(client: ZammadClient, api: Mock) -> None:
    api.knowledge_bases_answers.find_answer.return_value = {
        "id": ROOT_ANSWER_ID,
        "assets": {
            "KnowledgeBaseAnswerTranslationContent": {"500": {"id": ROOT_CONTENT_ID, "body": "<p>Open settings</p>"}}
        },
    }

    answer = client.get_kb_answer(KB_ID, ROOT_ANSWER_ID)

    api.knowledge_bases_answers.find_answer.assert_called_once_with(
        KB_ID, ROOT_ANSWER_ID, include_content_id=ROOT_CONTENT_ID
    )
    assert answer["title"] == "Reset your password"
    assert answer["body"] == "<p>Open settings</p>"
    assert answer["category_id"] == ROOT_CATEGORY_ID
    assert answer["published_at"] == "2024-01-01T00:00:00Z"


def test_get_kb_answer_unknown_id_raises_without_fetching(client: ZammadClient, api: Mock) -> None:
    with pytest.raises(KnowledgeBaseNotFoundError):
        client.get_kb_answer(KB_ID, 999)

    api.knowledge_bases_answers.find_answer.assert_not_called()


def test_get_kb_answer_rejects_missing_content(client: ZammadClient, api: Mock) -> None:
    api.knowledge_bases_answers.find_answer.return_value = {"id": ROOT_ANSWER_ID, "assets": {}}

    with pytest.raises(KnowledgeBaseResponseError):
        client.get_kb_answer(KB_ID, ROOT_ANSWER_ID)
