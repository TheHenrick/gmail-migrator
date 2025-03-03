"""Tests for API routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.app import create_app


@pytest.fixture()
def client():
    """Fixture for FastAPI test client."""
    app = create_app(testing=True)
    return TestClient(app)


@pytest.fixture()
def mock_oauth_flow():
    """Fixture for mock OAuth flow."""
    with patch("app.services.gmail.auth.OAuthFlow") as mock:
        mock_flow = MagicMock()
        mock_flow.get_authorization_url.return_value = (
            "https://mock-auth-url.com",
            "test_state",
        )
        mock_flow.exchange_code.return_value = {"credentials": "mock_credentials"}
        mock.return_value = mock_flow
        yield mock_flow


@pytest.fixture()
def mock_gmail_client():
    """Fixture for mock Gmail client."""
    with patch("app.dependencies.GmailClient") as mock:
        mock_client = MagicMock()
        mock_client.get_email_list.return_value = {
            "messages": [
                {"id": "msg1", "snippet": "Test email 1"},
                {"id": "msg2", "snippet": "Test email 2"},
            ],
            "next_page_token": None,
        }
        mock_client.get_email_content.return_value = {
            "id": "msg1",
            "subject": "Test Subject",
            "from": "sender@example.com",
            "date": "2023-03-30T12:00:00Z",
            "body": {"plain": "Test email body", "html": "<div>Test email body</div>"},
            "attachments": [],
        }
        mock.return_value = mock_client
        yield mock_client


def test_auth_url(client, mock_oauth_flow):
    """Test auth URL endpoint."""
    with patch("app.api.routers.gmail.oauth_flow", mock_oauth_flow):
        response = client.get("/gmail/auth-url")
        data = response.json()

        assert response.status_code == 200
        assert "auth_url" in data
        assert data["auth_url"] == "https://mock-auth-url.com"


def test_auth_callback(client, mock_oauth_flow):
    """Test auth callback endpoint."""
    with patch("app.api.routers.gmail.oauth_flow", mock_oauth_flow):
        response = client.get("/gmail/auth-callback?code=test_code")
        data = response.json()

        assert response.status_code == 200
        assert "message" in data
        mock_oauth_flow.exchange_code.assert_called_once_with("test_code")


def test_get_emails(client, mock_gmail_client):
    """Test getting emails endpoint."""
    with patch("app.dependencies.get_gmail_client", return_value=mock_gmail_client):
        response = client.get(
            "/gmail/emails?query=test&max_results=10",
            headers={"Authorization": "Bearer test_token"},
        )
        data = response.json()

        assert response.status_code == 200
        assert len(data) == 2
        mock_gmail_client.get_email_list.assert_called_once_with(
            query="test", max_results=10, page_token=None
        )


def test_get_email_detail(client, mock_gmail_client):
    """Test getting email detail endpoint."""
    with patch("app.dependencies.get_gmail_client", return_value=mock_gmail_client):
        response = client.get(
            "/gmail/emails/msg1", headers={"Authorization": "Bearer test_token"}
        )
        data = response.json()

        assert response.status_code == 200
        assert data["id"] == "msg1"
        assert data["subject"] == "Test Subject"
        mock_gmail_client.get_email_content.assert_called_once_with("msg1")


def test_unauthorized_access(client):
    """Test unauthorized access to protected endpoints."""
    response = client.get("/gmail/emails")
    data = response.json()

    assert response.status_code == 401
    assert "detail" in data
