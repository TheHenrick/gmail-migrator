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
        response = client.post("/gmail/auth-url")
        data = response.json()

        assert response.status_code == 200
        assert "auth_url" in data


def test_auth_callback_post(client, mock_oauth_flow):
    """Test auth callback endpoint with POST method."""
    with (
        patch("app.api.routers.gmail.oauth_flow", mock_oauth_flow),
        patch("app.api.routers.gmail.exchange_code") as mock_exchange_code,
    ):
        mock_exchange_code.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        }

        # Mock the fetch_user_profile function to return a JSON string
        with patch(
            "app.api.routers.gmail.fetch_user_profile",
            return_value='{"name":"Test User","email":"test@example.com","picture":""}',
        ):
            response = client.post("/gmail/auth-callback?code=test_code")

            # Test for HTML response
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/html; charset=utf-8"
            assert "Authentication Successful" in response.text
            assert "gmailToken" in response.text
            assert "test_token" in response.text


def test_auth_callback_get(client, mock_oauth_flow):
    """Test auth callback endpoint with GET method."""
    with (
        patch("app.api.routers.gmail.oauth_flow", mock_oauth_flow),
        patch("app.api.routers.gmail.exchange_code") as mock_exchange_code,
    ):
        mock_exchange_code.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        }

        # Mock the fetch_user_profile function to return a JSON string
        with patch(
            "app.api.routers.gmail.fetch_user_profile",
            return_value='{"name":"Test User","email":"test@example.com","picture":""}',
        ):
            response = client.get("/gmail/auth-callback?code=test_code")

            # Test for HTML response
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/html; charset=utf-8"
            assert "Authentication Successful" in response.text
            assert "gmailToken" in response.text
            assert "test_token" in response.text


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
