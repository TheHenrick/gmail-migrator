"""Tests for API routes."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.app import create_app


@pytest.fixture()
def client():
    """Fixture for Flask test client."""
    app = create_app(testing=True)
    with app.test_client() as client:
        yield client


@pytest.fixture()
def mock_oauth_flow():
    """Fixture for mock OAuth flow."""
    with patch("app.api.routers.gmail.OAuthFlow") as mock:
        mock_flow = MagicMock()
        mock_flow.get_authorization_url.return_value = "https://mock-auth-url.com"
        mock_flow.exchange_code.return_value = {"credentials": "mock_credentials"}
        mock.return_value = mock_flow
        yield mock_flow


@pytest.fixture()
def mock_gmail_client():
    """Fixture for mock Gmail client."""
    with patch("app.api.routers.gmail.GmailClient") as mock:
        mock_client = MagicMock()
        mock_client.get_email_list.return_value = {
            "messages": [
                {"id": "msg1", "snippet": "Test email 1"},
                {"id": "msg2", "snippet": "Test email 2"},
            ],
            "nextPageToken": None,
        }
        mock_client.get_email_content.return_value = {
            "id": "msg1",
            "subject": "Test Subject",
            "from": "sender@example.com",
            "date": "2023-03-30T12:00:00Z",
            "body_text": "Test email body",
            "body_html": "<div>Test email body</div>",
            "attachments": [],
        }
        mock.return_value = mock_client
        yield mock_client


def test_auth_url(client, mock_oauth_flow):
    """Test auth URL endpoint."""
    response = client.get("/api/gmail/auth-url")
    data = json.loads(response.data)

    assert response.status_code == 200
    assert "auth_url" in data
    assert data["auth_url"] == "https://mock-auth-url.com"


def test_auth_callback(client, mock_oauth_flow):
    """Test auth callback endpoint."""
    response = client.get("/api/gmail/auth-callback?code=test_code")
    data = json.loads(response.data)

    assert response.status_code == 200
    assert "message" in data
    mock_oauth_flow.exchange_code.assert_called_once_with("test_code")


def test_get_emails(client, mock_gmail_client):
    """Test getting emails endpoint."""
    with patch("app.api.routers.gmail.get_session_credentials", return_value=True):
        response = client.get("/api/gmail/emails?query=test&max_results=10")
        data = json.loads(response.data)

        assert response.status_code == 200
        assert "messages" in data
        assert len(data["messages"]) == 2
        mock_gmail_client.get_email_list.assert_called_once_with(
            query="test", max_results=10, page_token=None
        )


def test_get_email_detail(client, mock_gmail_client):
    """Test getting email detail endpoint."""
    with patch("app.api.routers.gmail.get_session_credentials", return_value=True):
        response = client.get("/api/gmail/emails/msg1")
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["id"] == "msg1"
        assert data["subject"] == "Test Subject"
        mock_gmail_client.get_email_content.assert_called_once_with("msg1")


def test_unauthorized_access(client):
    """Test unauthorized access to protected endpoints."""
    with patch("app.api.routers.gmail.get_session_credentials", return_value=None):
        response = client.get("/api/gmail/emails")
        data = json.loads(response.data)

        assert response.status_code == 401
        assert "error" in data
