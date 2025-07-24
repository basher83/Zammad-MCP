"""Tests for ZammadClient methods to improve coverage."""

import os
from unittest.mock import Mock, patch

import pytest

from mcp_zammad.client import ConfigException, ZammadClient


class TestZammadClientMethods:
    """Test ZammadClient methods."""

    @pytest.fixture
    def mock_zammad_api(self):
        """Mock the underlying zammad_py.ZammadAPI."""
        with patch("mcp_zammad.client.ZammadAPI") as mock_api:
            yield mock_api

    def test_get_organization(self, mock_zammad_api):
        """Test get_organization method."""
        mock_instance = Mock()
        mock_instance.organization.find.return_value = {
            "id": 1,
            "name": "Test Org",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            http_token="test-token"
        )
        
        result = client.get_organization(1)
        
        assert result["id"] == 1
        assert result["name"] == "Test Org"
        mock_instance.organization.find.assert_called_once_with(1)

    def test_search_organizations(self, mock_zammad_api):
        """Test search_organizations method."""
        mock_instance = Mock()
        mock_instance.organization.search.return_value = [
            {"id": 1, "name": "Org 1"},
            {"id": 2, "name": "Org 2"}
        ]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            http_token="test-token"
        )
        
        result = client.search_organizations("test", page=1, per_page=25)
        
        assert len(result) == 2
        assert result[0]["name"] == "Org 1"
        mock_instance.organization.search.assert_called_once_with(
            query="test", page=1, per_page=25
        )

    def test_update_ticket(self, mock_zammad_api):
        """Test update_ticket method."""
        mock_instance = Mock()
        mock_instance.ticket.update.return_value = {
            "id": 1,
            "title": "Updated Title",
            "state": "open"
        }
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            http_token="test-token"
        )
        
        result = client.update_ticket(
            1,
            title="Updated Title",
            state="open"
        )
        
        assert result["title"] == "Updated Title"
        mock_instance.ticket.update.assert_called_once_with(
            1,
            {"title": "Updated Title", "state": "open"}
        )

    def test_get_groups(self, mock_zammad_api):
        """Test get_groups method."""
        mock_instance = Mock()
        mock_instance.group.all.return_value = [
            {"id": 1, "name": "Users"},
            {"id": 2, "name": "Support"}
        ]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            http_token="test-token"
        )
        
        result = client.get_groups()
        
        assert len(result) == 2
        assert result[0]["name"] == "Users"
        mock_instance.group.all.assert_called_once()

    def test_get_ticket_states(self, mock_zammad_api):
        """Test get_ticket_states method."""
        mock_instance = Mock()
        mock_instance.ticket_state.all.return_value = [
            {"id": 1, "name": "new"},
            {"id": 2, "name": "open"}
        ]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            http_token="test-token"
        )
        
        result = client.get_ticket_states()
        
        assert len(result) == 2
        assert result[0]["name"] == "new"
        mock_instance.ticket_state.all.assert_called_once()

    def test_get_ticket_priorities(self, mock_zammad_api):
        """Test get_ticket_priorities method."""
        mock_instance = Mock()
        mock_instance.ticket_priority.all.return_value = [
            {"id": 1, "name": "1 low"},
            {"id": 2, "name": "2 normal"}
        ]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            http_token="test-token"
        )
        
        result = client.get_ticket_priorities()
        
        assert len(result) == 2
        assert result[0]["name"] == "1 low"
        mock_instance.ticket_priority.all.assert_called_once()

    def test_search_users(self, mock_zammad_api):
        """Test search_users method."""
        mock_instance = Mock()
        mock_instance.user.search.return_value = [
            {"id": 1, "email": "user1@example.com"},
            {"id": 2, "email": "user2@example.com"}
        ]
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            http_token="test-token"
        )
        
        result = client.search_users("test", page=1, per_page=10)
        
        assert len(result) == 2
        assert result[0]["email"] == "user1@example.com"
        mock_instance.user.search.assert_called_once_with(
            query="test", page=1, per_page=10
        )

    def test_get_current_user(self, mock_zammad_api):
        """Test get_current_user method."""
        mock_instance = Mock()
        mock_instance.user.me.return_value = {
            "id": 1,
            "email": "current@example.com",
            "firstname": "Current",
            "lastname": "User"
        }
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            http_token="test-token"
        )
        
        result = client.get_current_user()
        
        assert result["email"] == "current@example.com"
        mock_instance.user.me.assert_called_once()

    def test_add_ticket_tag(self, mock_zammad_api):
        """Test add_ticket_tag method."""
        mock_instance = Mock()
        mock_instance.tag.add.return_value = {"success": True}
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            http_token="test-token"
        )
        
        result = client.add_ticket_tag(1, "urgent")
        
        assert result["success"] is True
        mock_instance.tag.add.assert_called_once_with(
            object="Ticket",
            o_id=1,
            item="urgent"
        )

    def test_remove_ticket_tag(self, mock_zammad_api):
        """Test remove_ticket_tag method."""
        mock_instance = Mock()
        mock_instance.tag.remove.return_value = {"success": True}
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            http_token="test-token"
        )
        
        result = client.remove_ticket_tag(1, "urgent")
        
        assert result["success"] is True
        mock_instance.tag.remove.assert_called_once_with(
            object="Ticket",
            o_id=1,
            item="urgent"
        )

    def test_oauth2_authentication(self, mock_zammad_api):
        """Test OAuth2 authentication."""
        mock_zammad_api.return_value = Mock()

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            oauth2_token="oauth-token"
        )
        
        assert client.oauth2_token == "oauth-token"
        mock_zammad_api.assert_called_once_with(
            url="https://test.zammad.com/api/v1",
            oauth2_token="oauth-token"
        )

    def test_username_password_authentication(self, mock_zammad_api):
        """Test username/password authentication."""
        mock_zammad_api.return_value = Mock()

        client = ZammadClient(
            url="https://test.zammad.com/api/v1",
            username="testuser",
            password="testpass"
        )
        
        assert client.username == "testuser"
        assert client.password == "testpass"
        mock_zammad_api.assert_called_once_with(
            url="https://test.zammad.com/api/v1",
            username="testuser",
            password="testpass"
        )