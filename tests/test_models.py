"""Tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from mcp_zammad.models import ArticleCreate, TicketCreate, TicketUpdate


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
