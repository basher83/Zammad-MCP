"""Tests for ZammadClient methods to improve coverage."""

import os
import pathlib
from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest

from mcp_zammad.client import ZammadClient

# Test constants to avoid magic numbers
EXPECTED_TWO_RESULTS = 2
EXPECTED_THREE_RESULTS = 3


class TestZammadClientMethods:
    """Test ZammadClient methods."""

    @pytest.fixture
    def mock_zammad_api(self) -> Generator[Mock, None, None]:
        """Mock the underlying zammad_py.ZammadAPI."""
        with patch("mcp_zammad.client.ZammadAPI") as mock_api:
            yield mock_api

    def test_get_organization(self, mock_zammad_api: Mock) -> None:
        """Test get_organization method."""
        mock_instance = Mock()
        mock_instance.organization.find.return_value = {
            "id": 1,
            "name": "Test Org",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.get_organization(1)

        assert result["id"] == 1
        assert result["name"] == "Test Org"
        mock_instance.organization.find.assert_called_once_with(1)

    def test_search_organizations(self, mock_zammad_api: Mock) -> None:
        """Test search_organizations method."""
        mock_instance = Mock()
        mock_instance.organization.search.return_value = [{"id": 1, "name": "Org 1"}, {"id": 2, "name": "Org 2"}]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.search_organizations("test", page=1, per_page=25)

        assert len(result) == EXPECTED_TWO_RESULTS
        assert result[0]["name"] == "Org 1"
        mock_instance.organization.search.assert_called_once_with(
            "test", filters={"page": 1, "per_page": 25, "expand": True}
        )

    def test_update_ticket(self, mock_zammad_api: Mock) -> None:
        """Test update_ticket method."""
        mock_instance = Mock()
        mock_instance.ticket.update.return_value = {"id": 1, "title": "Updated Title", "state": "open"}
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.update_ticket(1, title="Updated Title", state="open")

        assert result["title"] == "Updated Title"
        mock_instance.ticket.update.assert_called_once_with(1, {"title": "Updated Title", "state": "open"})

    def test_get_groups(self, mock_zammad_api: Mock) -> None:
        """Test get_groups method."""
        mock_instance = Mock()
        mock_instance.group.all.return_value = [{"id": 1, "name": "Users"}, {"id": 2, "name": "Support"}]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.get_groups()

        assert len(result) == 2
        assert result[0]["name"] == "Users"
        mock_instance.group.all.assert_called_once()

    def test_get_ticket_states(self, mock_zammad_api: Mock) -> None:
        """Test get_ticket_states method."""
        mock_instance = Mock()
        mock_instance.ticket_state.all.return_value = [{"id": 1, "name": "new"}, {"id": 2, "name": "open"}]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.get_ticket_states()

        assert len(result) == 2
        assert result[0]["name"] == "new"
        mock_instance.ticket_state.all.assert_called_once()

    def test_get_ticket_priorities(self, mock_zammad_api: Mock) -> None:
        """Test get_ticket_priorities method."""
        mock_instance = Mock()
        mock_instance.ticket_priority.all.return_value = [{"id": 1, "name": "1 low"}, {"id": 2, "name": "2 normal"}]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.get_ticket_priorities()

        assert len(result) == 2
        assert result[0]["name"] == "1 low"
        mock_instance.ticket_priority.all.assert_called_once()

    def test_search_users(self, mock_zammad_api: Mock) -> None:
        """Test search_users method."""
        mock_instance = Mock()
        mock_instance.user.search.return_value = [
            {"id": 1, "email": "user1@example.com"},
            {"id": 2, "email": "user2@example.com"},
        ]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.search_users("test", page=1, per_page=10)

        assert len(result) == 2
        assert result[0]["email"] == "user1@example.com"
        mock_instance.user.search.assert_called_once_with("test", filters={"page": 1, "per_page": 10, "expand": True})

    def test_get_current_user(self, mock_zammad_api: Mock) -> None:
        """Test get_current_user method."""
        mock_instance = Mock()
        mock_instance.user.me.return_value = {
            "id": 1,
            "email": "current@example.com",
            "firstname": "Current",
            "lastname": "User",
        }
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.get_current_user()

        assert result["email"] == "current@example.com"
        mock_instance.user.me.assert_called_once()

    def test_add_ticket_tag(self, mock_zammad_api: Mock) -> None:
        """Test add_ticket_tag method."""
        mock_instance = Mock()
        mock_instance.ticket_tag.add.return_value = {"success": True}
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.add_ticket_tag(1, "urgent")

        assert result["success"] is True
        mock_instance.ticket_tag.add.assert_called_once_with(1, "urgent")

    def test_remove_ticket_tag(self, mock_zammad_api: Mock) -> None:
        """Test remove_ticket_tag method."""
        mock_instance = Mock()
        mock_instance.ticket_tag.remove.return_value = {"success": True}
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.remove_ticket_tag(1, "urgent")

        assert result["success"] is True
        mock_instance.ticket_tag.remove.assert_called_once_with(1, "urgent")

    @patch.dict(os.environ, {}, clear=True)
    def test_oauth2_authentication(self, mock_zammad_api: Mock) -> None:
        """Test OAuth2 authentication."""
        mock_zammad_api.return_value = Mock()

        client = ZammadClient(url="https://test.zammad.com/api/v1", oauth2_token="oauth-token")

        assert client.oauth2_token == "oauth-token"
        mock_zammad_api.assert_called_once_with(
            url="https://test.zammad.com/api/v1",
            username=None,
            password=None,
            http_token=None,
            oauth2_token="oauth-token",
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_username_password_authentication(self, mock_zammad_api: Mock) -> None:
        """Test username/password authentication."""
        mock_zammad_api.return_value = Mock()

        client = ZammadClient(url="https://test.zammad.com/api/v1", username="testuser", password="testpass")

        assert client.username == "testuser"
        assert client.password == "testpass"
        mock_zammad_api.assert_called_once_with(
            url="https://test.zammad.com/api/v1",
            username="testuser",
            password="testpass",
            http_token=None,
            oauth2_token=None,
        )

    def test_read_secret_file(self, mock_zammad_api: Mock, tmp_path: pathlib.Path) -> None:
        """Test reading secrets from files."""
        # Create a temporary secret file
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("my-secret-token\n")

        with patch.dict(os.environ, {"ZAMMAD_HTTP_TOKEN_FILE": str(secret_file)}):
            mock_zammad_api.return_value = Mock()

            client = ZammadClient(url="https://test.zammad.com/api/v1")

            assert client.http_token == "my-secret-token"

    def test_read_secret_file_not_found(self, mock_zammad_api: Mock) -> None:
        """Test handling of missing secret file."""
        with patch.dict(
            os.environ,
            {
                "ZAMMAD_URL": "https://test.zammad.com/api/v1",
                "ZAMMAD_HTTP_TOKEN_FILE": "/nonexistent/file.txt",
                "ZAMMAD_HTTP_TOKEN": "fallback-token",
            },
        ):
            mock_zammad_api.return_value = Mock()

            # Should fall back to direct env var
            client = ZammadClient(url="https://test.zammad.com/api/v1")

            assert client.http_token == "fallback-token"

    def test_search_tickets_with_all_filters(self, mock_zammad_api: Mock) -> None:
        """Test search_tickets with all filter parameters."""
        mock_instance = Mock()
        mock_instance.ticket.search.return_value = [{"id": 1, "title": "Test Ticket"}]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.search_tickets(
            query="test",
            state="open",
            priority="high",
            group="Support",
            owner="agent1",
            customer="customer@example.com",
            page=2,
            per_page=50,
        )

        assert len(result) == 1
        expected_query = "test AND state.name:open AND priority.name:high AND group.name:Support AND owner.login:agent1 AND customer.email:customer@example.com"
        mock_instance.ticket.search.assert_called_once_with(
            expected_query, filters={"page": 2, "per_page": 50, "expand": True}
        )

    def test_search_tickets_no_query(self, mock_zammad_api: Mock) -> None:
        """Test search_tickets with no query uses ticket.all()."""
        mock_instance = Mock()
        mock_instance.ticket.all.return_value = [{"id": 1, "title": "Test Ticket"}]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.search_tickets()

        assert len(result) == 1
        mock_instance.ticket.all.assert_called_once_with(filters={"page": 1, "per_page": 25, "expand": True})

    def test_get_ticket_with_articles(self, mock_zammad_api: Mock) -> None:
        """Test get_ticket with article pagination."""
        mock_instance = Mock()
        mock_instance.ticket.find.return_value = {"id": 1, "title": "Test Ticket"}
        mock_instance.ticket.articles.return_value = [
            {"id": 1, "body": "Article 1"},
            {"id": 2, "body": "Article 2"},
            {"id": 3, "body": "Article 3"},
            {"id": 4, "body": "Article 4"},
            {"id": 5, "body": "Article 5"},
        ]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        # Test with limit
        result = client.get_ticket(1, include_articles=True, article_limit=2, article_offset=1)

        assert result["id"] == 1
        assert len(result["articles"]) == 2
        assert result["articles"][0]["body"] == "Article 2"
        assert result["articles"][1]["body"] == "Article 3"

    def test_get_ticket_all_articles(self, mock_zammad_api: Mock) -> None:
        """Test get_ticket with all articles."""
        mock_instance = Mock()
        mock_instance.ticket.find.return_value = {"id": 1, "title": "Test Ticket"}
        mock_instance.ticket.articles.return_value = [{"id": 1, "body": "Article 1"}, {"id": 2, "body": "Article 2"}]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        # Test with -1 (all articles)
        result = client.get_ticket(1, include_articles=True, article_limit=-1)

        assert len(result["articles"]) == 2

    def test_create_ticket(self, mock_zammad_api: Mock) -> None:
        """Test create_ticket method."""
        mock_instance = Mock()
        mock_instance.ticket.create.return_value = {"id": 1, "title": "New Ticket", "state": "new"}
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.create_ticket(
            title="New Ticket",
            group="Support",
            customer="customer@example.com",
            article_body="Please help!",
            state="open",
            priority="3 high",
            article_type="email",
            article_internal=True,
        )

        assert result["id"] == 1
        mock_instance.ticket.create.assert_called_once_with(
            {
                "title": "New Ticket",
                "group": "Support",
                "customer": "customer@example.com",
                "state": "open",
                "priority": "3 high",
                "article": {"body": "Please help!", "type": "email", "internal": True},
            }
        )

    def test_add_article(self, mock_zammad_api: Mock) -> None:
        """Test add_article method."""
        mock_instance = Mock()
        mock_instance.ticket_article.create.return_value = {"id": 1, "body": "Response", "type": "email"}
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.add_article(
            ticket_id=1, body="Response", article_type="email", internal=True, sender="Customer"
        )

        assert result["id"] == 1
        mock_instance.ticket_article.create.assert_called_once_with(
            {"ticket_id": 1, "body": "Response", "type": "email", "internal": True, "sender": "Customer"}
        )

    def test_get_user(self, mock_zammad_api: Mock) -> None:
        """Test get_user method."""
        mock_instance = Mock()
        mock_instance.user.find.return_value = {
            "id": 1,
            "email": "user@example.com",
            "firstname": "Test",
            "lastname": "User",
        }
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.get_user(1)

        assert result["email"] == "user@example.com"
        mock_instance.user.find.assert_called_once_with(1)

    def test_get_ticket_tags(self, mock_zammad_api: Mock) -> None:
        """Test get_ticket_tags method."""
        mock_instance = Mock()
        mock_instance.ticket.tags.return_value = {"tags": ["urgent", "customer-issue", "bug"]}
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        result = client.get_ticket_tags(1)

        assert len(result) == 3
        assert "urgent" in result
        mock_instance.ticket.tags.assert_called_once_with(1)

    def test_update_ticket_state_error_handling(self, mock_zammad_api: Mock) -> None:
        """Test update_ticket with special state handling."""
        mock_instance = Mock()

        # Test with string state (error path)
        mock_instance.ticket.update.side_effect = Exception("State error")
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        # This should handle the exception internally and retry
        with pytest.raises(Exception, match="State error"):
            client.update_ticket(1, state="closed")

    def test_update_ticket_priority_error_handling(self, mock_zammad_api: Mock) -> None:
        """Test update_ticket with special priority handling."""
        mock_instance = Mock()

        # Test with string priority (error path)
        mock_instance.ticket.update.side_effect = Exception("Priority error")
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        # This should handle the exception internally and retry
        with pytest.raises(Exception, match="Priority error"):
            client.update_ticket(1, priority="1 low")

    def test_update_ticket_group_error_handling(self, mock_zammad_api: Mock) -> None:
        """Test update_ticket with special group handling."""
        mock_instance = Mock()

        # Test with string group (error path)
        mock_instance.ticket.update.side_effect = Exception("Group error")
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        # This should handle the exception internally and retry
        with pytest.raises(Exception, match="Group error"):
            client.update_ticket(1, group="Support")
