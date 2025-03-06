"""Tests for the Outlook API router."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.outlook.auth import OutlookAuthManager


@pytest.fixture()
def test_client():
    """Fixture for a FastAPI test client."""
    return TestClient(app)


@pytest.fixture()
def mock_outlook_client():
    """Fixture for a mock Outlook client."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture()
def mock_gmail_client():
    """Fixture for a mock Gmail client."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture()
def mock_auth_manager():
    """Fixture for a mock Outlook auth manager."""
    mock_manager = MagicMock(spec=OutlookAuthManager)
    mock_manager.get_auth_url.return_value = "https://login.microsoftonline.com/auth"
    mock_manager.get_token_from_code.return_value = {
        "access_token": "mock_access_token",
        "refresh_token": "mock_refresh_token",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "Mail.Read Mail.ReadWrite",
    }
    return mock_manager


@pytest.mark.unit()
@pytest.mark.outlook()
class TestOutlookRouter:
    """Test suite for the Outlook API router."""

    @patch("app.api.routers.outlook.outlook_oauth_flow")
    def test_get_auth_url_default(self, mock_oauth_flow, test_client):
        """Test getting auth URL with default OAuth flow."""
        mock_oauth_flow.get_auth_url.return_value = "https://login.microsoftonline.com/auth"

        response = test_client.post("/outlook/auth-url")

        assert response.status_code == 200
        assert response.json() == {"auth_url": "https://login.microsoftonline.com/auth"}
        mock_oauth_flow.get_auth_url.assert_called_once()

    @patch("app.api.routers.outlook.OutlookAuthManager")
    def test_get_auth_url_custom_config(self, mock_auth_manager_class, test_client, mock_auth_manager):
        """Test getting auth URL with custom OAuth config."""
        mock_auth_manager_class.return_value = mock_auth_manager

        response = test_client.post(
            "/outlook/auth-url",
            json={
                "client_id": "custom_client_id",
                "client_secret": "custom_client_secret",
                "redirect_uri": "http://localhost:8000/custom-callback",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"auth_url": "https://login.microsoftonline.com/auth"}
        mock_auth_manager_class.assert_called_once_with(
            client_id="custom_client_id",
            client_secret="custom_client_secret",
            redirect_uri="http://localhost:8000/custom-callback",
        )
        mock_auth_manager.get_auth_url.assert_called_once()

    @patch("app.api.routers.outlook.outlook_oauth_flow")
    def test_get_auth_url_error(self, mock_oauth_flow, test_client):
        """Test error handling when getting auth URL."""
        mock_oauth_flow.get_auth_url.side_effect = Exception("Auth error")

        response = test_client.post("/outlook/auth-url")

        assert response.status_code == 500
        assert "Auth error" in response.json()["detail"]

    @pytest.mark.auth()
    @patch("app.api.routers.outlook.outlook_oauth_flow")
    def test_auth_callback_default(self, mock_oauth_flow, test_client):
        """Test auth callback with default OAuth flow."""
        mock_oauth_flow.get_token_from_code.return_value = {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "Mail.Read Mail.ReadWrite",
        }

        response = test_client.post("/outlook/auth-callback?code=mock_code")

        assert response.status_code == 200
        assert response.json() == {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "Mail.Read Mail.ReadWrite",
        }
        mock_oauth_flow.get_token_from_code.assert_called_once_with("mock_code")

    @pytest.mark.auth()
    @patch("app.api.routers.outlook.OutlookAuthManager")
    def test_auth_callback_custom_config(self, mock_auth_manager_class, test_client, mock_auth_manager):
        """Test auth callback with custom OAuth config."""
        mock_auth_manager_class.return_value = mock_auth_manager

        response = test_client.post(
            "/outlook/auth-callback?code=mock_code",
            json={
                "client_id": "custom_client_id",
                "client_secret": "custom_client_secret",
                "redirect_uri": "http://localhost:8000/custom-callback",
            },
        )

        assert response.status_code == 200
        assert "access_token" in response.json()
        mock_auth_manager_class.assert_called_once_with(
            client_id="custom_client_id",
            client_secret="custom_client_secret",
            redirect_uri="http://localhost:8000/custom-callback",
        )
        mock_auth_manager.get_token_from_code.assert_called_once_with("mock_code")

    @pytest.mark.auth()
    @patch("app.api.routers.outlook.outlook_oauth_flow")
    def test_auth_callback_error(self, mock_oauth_flow, test_client):
        """Test error handling in auth callback."""
        mock_oauth_flow.get_token_from_code.side_effect = Exception("Exchange error")

        response = test_client.post("/outlook/auth-callback?code=mock_code")

        assert response.status_code == 500
        assert "Exchange error" in response.json()["detail"]

    @patch("app.dependencies.get_outlook_client")
    def test_list_folders(self, mock_get_client, test_client, mock_outlook_client):
        """Test listing folders."""
        mock_get_client.return_value = mock_outlook_client
        mock_outlook_client.get_folders.return_value = [
            {
                "id": "folder1",
                "displayName": "Inbox",
                "parentFolderId": None,
                "childFolderCount": 2,
                "totalItemCount": 100,
                "unreadItemCount": 10,
            },
            {
                "id": "folder2",
                "displayName": "Sent Items",
                "parentFolderId": None,
                "childFolderCount": 0,
                "totalItemCount": 50,
                "unreadItemCount": 0,
            },
        ]

        response = test_client.get("/outlook/folders")

        assert response.status_code == 200
        folders = response.json()
        assert len(folders) == 2
        assert folders[0]["id"] == "folder1"
        assert folders[0]["display_name"] == "Inbox"
        assert folders[1]["id"] == "folder2"
        assert folders[1]["display_name"] == "Sent Items"
        mock_outlook_client.get_folders.assert_called_once()

    @patch("app.dependencies.get_outlook_client")
    def test_list_folders_error(self, mock_get_client, test_client, mock_outlook_client):
        """Test error handling when listing folders."""
        mock_get_client.return_value = mock_outlook_client
        mock_outlook_client.get_folders.side_effect = Exception("Folder error")

        response = test_client.get("/outlook/folders")

        assert response.status_code == 500
        assert "Folder error" in response.json()["detail"]

    @patch("app.dependencies.get_outlook_client")
    def test_create_folder(self, mock_get_client, test_client, mock_outlook_client):
        """Test creating a folder."""
        mock_get_client.return_value = mock_outlook_client
        mock_outlook_client.create_folder.return_value = {
            "id": "new_folder",
            "displayName": "Test Folder",
            "parentFolderId": None,
            "childFolderCount": 0,
            "totalItemCount": 0,
            "unreadItemCount": 0,
        }

        response = test_client.post("/outlook/folders?name=Test%20Folder")

        assert response.status_code == 200
        folder = response.json()
        assert folder["id"] == "new_folder"
        assert folder["display_name"] == "Test Folder"
        mock_outlook_client.create_folder.assert_called_once_with("Test Folder", None)

    @patch("app.dependencies.get_outlook_client")
    def test_create_subfolder(self, mock_get_client, test_client, mock_outlook_client):
        """Test creating a subfolder."""
        mock_get_client.return_value = mock_outlook_client
        mock_outlook_client.create_folder.return_value = {
            "id": "new_subfolder",
            "displayName": "Test Subfolder",
            "parentFolderId": "parent_folder",
            "childFolderCount": 0,
            "totalItemCount": 0,
            "unreadItemCount": 0,
        }

        response = test_client.post("/outlook/folders?name=Test%20Subfolder&parent_folder_id=parent_folder")

        assert response.status_code == 200
        folder = response.json()
        assert folder["id"] == "new_subfolder"
        assert folder["display_name"] == "Test Subfolder"
        assert folder["parent_folder_id"] == "parent_folder"
        mock_outlook_client.create_folder.assert_called_once_with("Test Subfolder", "parent_folder")

    @patch("app.dependencies.get_outlook_client")
    def test_create_folder_error(self, mock_get_client, test_client, mock_outlook_client):
        """Test error handling when creating a folder."""
        mock_get_client.return_value = mock_outlook_client
        mock_outlook_client.create_folder.side_effect = Exception("Creation error")

        response = test_client.post("/outlook/folders?name=Test%20Folder")

        assert response.status_code == 500
        assert "Creation error" in response.json()["detail"]

    @patch("app.dependencies.get_gmail_client")
    @patch("app.dependencies.get_outlook_client")
    def test_migrate_email(
        self,
        mock_get_outlook,
        mock_get_gmail,
        test_client,
        mock_outlook_client,
        mock_gmail_client,
    ):
        """Test migrating a single email."""
        mock_get_outlook.return_value = mock_outlook_client
        mock_get_gmail.return_value = mock_gmail_client

        # Mock Gmail client responses
        gmail_email = {
            "id": "email123",
            "subject": "Test Email",
            "body": "<p>Test Body</p>",
            "to_address": "recipient@example.com",
            "has_attachments": True,
            "attachments": [{"id": "att1", "filename": "test.pdf"}],
        }
        mock_gmail_client.get_email.return_value = gmail_email
        mock_gmail_client.get_attachment.return_value = {
            "id": "att1",
            "filename": "test.pdf",
            "data": b"test content",
            "mime_type": "application/pdf",
        }

        # Mock Outlook client response
        mock_outlook_client.migrate_email.return_value = {"id": "outlook_email_id"}

        response = test_client.post("/outlook/migrate-email?email_id=email123")

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert result["gmail_id"] == "email123"
        assert result["outlook_id"] == "outlook_email_id"

        # Verify the correct calls were made
        mock_gmail_client.get_email.assert_called_once_with("email123")
        mock_gmail_client.get_attachment.assert_called_once_with("email123", "att1")
        mock_outlook_client.migrate_email.assert_called_once()

        # Check that the attachment was correctly passed
        call_args = mock_outlook_client.migrate_email.call_args[1]
        assert call_args["gmail_message"] == gmail_email
        assert len(call_args["attachments"]) == 1
        assert call_args["attachments"][0]["name"] == "test.pdf"
        assert call_args["attachments"][0]["content"] == b"test content"
        assert call_args["attachments"][0]["contentType"] == "application/pdf"

    @patch("app.dependencies.get_gmail_client")
    @patch("app.dependencies.get_outlook_client")
    def test_migrate_email_with_folder(
        self,
        mock_get_outlook,
        mock_get_gmail,
        test_client,
        mock_outlook_client,
        mock_gmail_client,
    ):
        """Test migrating an email to a specific folder."""
        mock_get_outlook.return_value = mock_outlook_client
        mock_get_gmail.return_value = mock_gmail_client

        # Mock Gmail client responses
        gmail_email = {
            "id": "email123",
            "subject": "Test Email",
            "body": "<p>Test Body</p>",
            "to_address": "recipient@example.com",
            "has_attachments": False,
        }
        mock_gmail_client.get_email.return_value = gmail_email

        # Mock Outlook client response
        mock_outlook_client.migrate_email.return_value = {"id": "outlook_email_id"}

        response = test_client.post("/outlook/migrate-email?email_id=email123&folder_id=folder123")

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"

        # Verify the folder_id was passed correctly
        call_args = mock_outlook_client.migrate_email.call_args[1]
        assert call_args["folder_id"] == "folder123"

    @patch("app.dependencies.get_gmail_client")
    @patch("app.dependencies.get_outlook_client")
    def test_migrate_email_error(
        self,
        mock_get_outlook,
        mock_get_gmail,
        test_client,
        mock_outlook_client,
        mock_gmail_client,
    ):
        """Test error handling when migrating an email."""
        mock_get_outlook.return_value = mock_outlook_client
        mock_get_gmail.return_value = mock_gmail_client

        mock_gmail_client.get_email.side_effect = Exception("Gmail error")

        response = test_client.post("/outlook/migrate-email?email_id=email123")

        assert response.status_code == 500
        assert "Gmail error" in response.json()["detail"]

    @patch("app.dependencies.get_gmail_client")
    @patch("app.dependencies.get_outlook_client")
    def test_batch_migrate(
        self,
        mock_get_outlook,
        mock_get_gmail,
        test_client,
        mock_outlook_client,
        mock_gmail_client,
    ):
        """Test batch migrating emails."""
        mock_get_outlook.return_value = mock_outlook_client
        mock_get_gmail.return_value = mock_gmail_client

        # Mock Gmail client responses
        gmail_email = {
            "id": "email123",
            "subject": "Test Email",
            "body": "<p>Test Body</p>",
            "to_address": "recipient@example.com",
            "has_attachments": False,
        }
        mock_gmail_client.get_email.return_value = gmail_email

        # Mock Outlook client response
        mock_outlook_client.migrate_email.return_value = {"id": "outlook_email_id"}

        response = test_client.post(
            "/outlook/batch-migrate",
            json=["email1", "email2", "email3"],
        )

        assert response.status_code == 200
        result = response.json()
        assert result["total"] == 3
        assert result["successful"] == 3
        assert result["failed"] == 0
        assert result["failed_ids"] == []

        # Verify the correct number of calls were made
        assert mock_gmail_client.get_email.call_count == 3
        assert mock_outlook_client.migrate_email.call_count == 3

    @patch("app.dependencies.get_gmail_client")
    @patch("app.dependencies.get_outlook_client")
    def test_batch_migrate_with_failures(
        self,
        mock_get_outlook,
        mock_get_gmail,
        test_client,
        mock_outlook_client,
        mock_gmail_client,
    ):
        """Test batch migrating emails with some failures."""
        mock_get_outlook.return_value = mock_outlook_client
        mock_get_gmail.return_value = mock_gmail_client

        # Set up the second email to fail
        class EmailRetrievalError(Exception):
            """Custom exception for email retrieval errors."""

            pass

        def get_email_side_effect(email_id):
            if email_id == "email2":
                error_msg = "Error with email2"
                raise EmailRetrievalError(error_msg)
            return {
                "id": email_id,
                "subject": "Test Email",
                "body": "<p>Test Body</p>",
                "to_address": "recipient@example.com",
                "has_attachments": False,
            }

        mock_gmail_client.get_email.side_effect = get_email_side_effect

        response = test_client.post(
            "/outlook/batch-migrate",
            json=["email1", "email2", "email3"],
        )

        assert response.status_code == 200
        result = response.json()
        assert result["total"] == 3
        assert result["successful"] == 2
        assert result["failed"] == 1
        assert result["failed_ids"] == ["email2"]

        # Verify the correct number of calls were made
        assert mock_gmail_client.get_email.call_count == 3
        assert mock_outlook_client.migrate_email.call_count == 2
