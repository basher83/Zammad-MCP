"""Tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from mcp_zammad.models import (
    ArticleCreate,
    AttachmentUpload,
    DeleteAttachmentParams,
    GetTicketParams,
    ResponseFormat,
    TicketCreate,
    TicketUpdate,
)


class TestTicketCreate:
    """Test TicketCreate model validation."""

    def test_html_sanitization_in_title(self):
        """Test that HTML is escaped in ticket title."""
        ticket = TicketCreate(
            title="<script>alert('XSS')</script>",
            group="Support",
            customer="test@example.com",
            article_body="Test body",
        )
        assert ticket.title == "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;"

    def test_html_sanitization_in_body(self):
        """Test that HTML is escaped in article body."""
        ticket = TicketCreate(
            title="Test ticket",
            group="Support",
            customer="test@example.com",
            article_body="<b>Bold</b> and <script>alert('XSS')</script>",
        )
        assert ticket.article_body == "&lt;b&gt;Bold&lt;/b&gt; and &lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;"

    def test_field_length_limits(self):
        """Test that field length limits are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            TicketCreate(
                title="x" * 201,  # Exceeds 200 char limit
                group="Support",
                customer="test@example.com",
                article_body="Test",
            )
        assert "String should have at most 200 characters" in str(exc_info.value)


class TestTicketUpdate:
    """Test TicketUpdate model validation."""

    def test_html_sanitization_in_title(self):
        """Test that HTML is escaped in title update."""
        update = TicketUpdate(title="<i>Important</i> Update")  # type: ignore[call-arg]
        assert update.title == "&lt;i&gt;Important&lt;/i&gt; Update"

    def test_none_title_not_sanitized(self):
        """Test that None title is not processed."""
        update = TicketUpdate(state="closed")  # type: ignore[call-arg]
        assert update.title is None

    def test_field_length_limits(self):
        """Test that field length limits are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            TicketUpdate(title="x" * 201)  # type: ignore[call-arg]  # Exceeds 200 char limit
        assert "String should have at most 200 characters" in str(exc_info.value)


class TestArticleCreate:
    """Test ArticleCreate model validation."""

    def test_html_sanitization_in_body(self):
        """Test that HTML is escaped in article body."""
        article = ArticleCreate(
            ticket_id=123,
            body="<div onclick='alert()'>Click me</div>",
        )
        assert article.body == "&lt;div onclick=&#x27;alert()&#x27;&gt;Click me&lt;/div&gt;"

    def test_ticket_id_validation(self):
        """Test that ticket_id must be positive."""
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreate(ticket_id=0, body="Test")
        assert "Input should be greater than 0" in str(exc_info.value)

    def test_field_length_limits(self):
        """Test that field length limits are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreate(
                ticket_id=123,
                body="x" * 100001,  # Exceeds 100000 char limit
            )
        assert "String should have at most 100000 characters" in str(exc_info.value)


def test_get_ticket_params_has_response_format():
    """GetTicketParams should support response_format parameter."""
    params = GetTicketParams(ticket_id=123, response_format=ResponseFormat.JSON)
    assert params.response_format == ResponseFormat.JSON

    # Test default is MARKDOWN
    params_default = GetTicketParams(ticket_id=123)
    assert params_default.response_format == ResponseFormat.MARKDOWN


class TestAttachmentUpload:
    """Tests for AttachmentUpload model."""

    def test_valid_attachment(self):
        """Test creating valid attachment with base64 data."""
        att = AttachmentUpload(
            filename="test.pdf",
            data="dGVzdA==",  # "test" in base64
            mime_type="application/pdf",
        )
        assert att.filename == "test.pdf"
        assert att.data == "dGVzdA=="
        assert att.mime_type == "application/pdf"

    def test_invalid_base64(self):
        """Test that invalid base64 data raises validation error."""
        with pytest.raises(ValidationError, match="Invalid base64"):
            AttachmentUpload(filename="test.pdf", data="not-valid-base64!!!", mime_type="application/pdf")

    def test_path_traversal_sanitization(self):
        """Test filename sanitization prevents path traversal."""
        att = AttachmentUpload(filename="../../../etc/passwd", data="dGVzdA==", mime_type="text/plain")
        assert att.filename == "passwd"  # Path components stripped
        assert "/" not in att.filename

    def test_null_byte_removal(self):
        """Test null bytes are removed from filename."""
        att = AttachmentUpload(filename="test\x00.pdf", data="dGVzdA==", mime_type="application/pdf")
        assert "\x00" not in att.filename
        assert att.filename == "test.pdf"


class TestArticleCreateWithAttachments:
    """Tests for ArticleCreate with attachments."""

    def test_article_with_valid_attachments(self):
        """Test creating article with valid attachments."""
        article = ArticleCreate(
            ticket_id=123,
            body="See attached",
            attachments=[AttachmentUpload(filename="doc.pdf", data="dGVzdA==", mime_type="application/pdf")],
        )
        assert article.ticket_id == 123
        assert article.body == "See attached"
        assert article.attachments is not None
        assert len(article.attachments) == 1
        assert article.attachments[0].filename == "doc.pdf"

    def test_too_many_attachments(self):
        """Test that >10 attachments raises validation error."""
        with pytest.raises(ValidationError):
            ArticleCreate(
                ticket_id=123,
                body="Too many files",
                attachments=[
                    AttachmentUpload(filename=f"file{i}.txt", data="dGVzdA==", mime_type="text/plain")
                    for i in range(11)  # 11 attachments - exceeds limit
                ],
            )

    def test_article_without_attachments(self):
        """Test creating article without attachments (backward compatibility)."""
        article = ArticleCreate(ticket_id=123, body="Simple comment")
        assert article.ticket_id == 123
        assert article.body == "Simple comment"
        assert article.attachments is None


class TestDeleteAttachmentParams:
    """Tests for DeleteAttachmentParams model."""

    def test_valid_params(self):
        """Test creating valid delete attachment parameters."""
        params = DeleteAttachmentParams(ticket_id=123, article_id=456, attachment_id=789)
        assert params.ticket_id == 123
        assert params.article_id == 456
        assert params.attachment_id == 789

    def test_invalid_ticket_id(self):
        """Test that ticket_id must be positive."""
        with pytest.raises(ValidationError, match="greater than 0"):
            DeleteAttachmentParams(ticket_id=0, article_id=456, attachment_id=789)


class TestDeleteAttachmentResult:
    """Tests for DeleteAttachmentResult model."""

    def test_successful_deletion(self):
        """Test creating successful deletion result."""
        from mcp_zammad.models import DeleteAttachmentResult

        result = DeleteAttachmentResult(
            success=True,
            ticket_id=123,
            article_id=456,
            attachment_id=789,
            message="Successfully deleted attachment 789 from article 456 in ticket 123",
        )
        assert result.success is True
        assert result.ticket_id == 123
        assert result.article_id == 456
        assert result.attachment_id == 789
        assert "Successfully deleted" in result.message

    def test_failed_deletion(self):
        """Test creating failed deletion result."""
        from mcp_zammad.models import DeleteAttachmentResult

        result = DeleteAttachmentResult(
            success=False,
            ticket_id=123,
            article_id=456,
            attachment_id=789,
            message="Failed to delete attachment 789",
        )
        assert result.success is False
        assert result.ticket_id == 123
        assert result.article_id == 456
        assert result.attachment_id == 789
        assert "Failed" in result.message
