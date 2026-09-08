"""Tests for case-insensitive constant inputs at public model boundaries."""

import pytest
from pydantic import ValidationError

from mcp_zammad.models import ArticleCreate, ArticleSender, ArticleType, GetTicketParams, ResponseFormat


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("MARKDOWN", ResponseFormat.MARKDOWN),
        ("Markdown", ResponseFormat.MARKDOWN),
        ("JSON", ResponseFormat.JSON),
        ("Json", ResponseFormat.JSON),
        ("json", ResponseFormat.JSON),
    ],
)
def test_response_format_accepts_any_case(raw: str, expected: ResponseFormat) -> None:
    """Response format input should resolve to the canonical enum member regardless of case."""
    params = GetTicketParams(ticket_id=1, response_format=raw)  # type: ignore[arg-type]
    assert params.response_format is expected
    assert params.response_format.value == expected.value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("NOTE", ArticleType.NOTE),
        ("Email", ArticleType.EMAIL),
        ("PHONE", ArticleType.PHONE),
    ],
)
def test_article_type_accepts_any_case(raw: str, expected: ArticleType) -> None:
    """Article type input should resolve to the canonical enum member regardless of case."""
    article = ArticleCreate(ticket_id=1, body="hi", article_type=raw)  # type: ignore[arg-type]
    assert article.article_type is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("agent", ArticleSender.AGENT),
        ("CUSTOMER", ArticleSender.CUSTOMER),
        ("system", ArticleSender.SYSTEM),
    ],
)
def test_article_sender_accepts_any_case_and_keeps_canonical_value(raw: str, expected: ArticleSender) -> None:
    """Sender input should resolve to the title-cased canonical value Zammad expects."""
    article = ArticleCreate(ticket_id=1, body="hi", sender=raw)  # type: ignore[arg-type]
    assert article.sender is expected
    assert article.sender.value == expected.value


@pytest.mark.parametrize(
    ("raw", "expected", "body", "expected_body"),
    [
        ("TEXT/HTML", "text/html", "<b>x</b>", "<b>x</b>"),
        ("Text/Plain", "text/plain", "<b>x</b>", "&lt;b&gt;x&lt;/b&gt;"),
    ],
)
def test_content_type_accepts_any_case(raw: str, expected: str, body: str, expected_body: str) -> None:
    """Content type input should normalize to the canonical literal and drive body sanitization."""
    article = ArticleCreate(ticket_id=1, body=body, content_type=raw)  # type: ignore[arg-type]
    assert article.content_type == expected
    assert article.body == expected_body


def test_invalid_response_format_rejected() -> None:
    """Case folding must not accept values outside the enum."""
    with pytest.raises(ValidationError, match="response_format"):
        GetTicketParams(ticket_id=1, response_format="xml")  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["article_type", "sender", "content_type"])
def test_invalid_article_constants_rejected(field: str) -> None:
    """Case folding must not accept values outside each article constant set."""
    with pytest.raises(ValidationError, match=field):
        ArticleCreate(ticket_id=1, body="hi", **{field: "bogus"})


def test_non_string_content_type_rejected() -> None:
    """Non-string content type input should still fail standard validation."""
    with pytest.raises(ValidationError, match="content_type"):
        ArticleCreate(ticket_id=1, body="hi", content_type=42)  # type: ignore[arg-type]


def test_schema_keeps_canonical_values() -> None:
    """Generated schemas should still advertise only canonical values."""
    ticket_schema = GetTicketParams.model_json_schema()
    article_schema = ArticleCreate.model_json_schema()
    assert ticket_schema["$defs"]["ResponseFormat"]["enum"] == ["markdown", "json"]
    assert article_schema["$defs"]["ArticleSender"]["enum"] == ["Agent", "Customer", "System"]
    assert article_schema["properties"]["content_type"]["enum"] == ["text/plain", "text/html"]
