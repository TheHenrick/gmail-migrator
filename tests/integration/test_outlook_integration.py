"""Integration tests for the Outlook service."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.outlook.client import OutlookClient


@pytest.fixture()
def test_client():
    """Fixture for a FastAPI test client."""
    return TestClient(app)


@pytest.mark.integration()
@pytest.mark.outlook()
class TestOutlookIntegration:
    """Integration tests for the Outlook service."""

    @patch("app.api.routers.outlook.outlook_oauth_flow")
    @patch("app.dependencies.get_outlook_client")
    @patch("app.dependencies.get_gmail_client")
    def test_full_migration_flow(
        self,
        mock_get_gmail,
        mock_get_outlook,
        mock_oauth_flow,
        test_client,
        mock_outlook_client,
        mock_gmail_client,
    ):
        """Test the full email migration flow from Gmail to Outlook."""
        # Set up mocks
        mock_get_gmail.return_value = mock_gmail_client
        mock_get_outlook.return_value = mock_outlook_client
        mock_oauth_flow.get_auth_url.return_value = (
            "https://login.microsoftonline.com/auth"
        )

        # Step 1: Get auth URL
        auth_url_response = test_client.post("/outlook/auth-url")
        assert auth_url_response.status_code == 200
        assert auth_url_response.json() == {
            "auth_url": "https://login.microsoftonline.com/auth"
        }

        # Step 2: Create a folder in Outlook
        folder_response = test_client.post("/outlook/folders?name=Migrated%20Emails")
        assert folder_response.status_code == 200
        folder = folder_response.json()
        assert folder["display_name"] == "Test Folder"  # Using the mock response
        folder_id = folder["id"]

        # Step 3: Migrate a single email
        migrate_response = test_client.post(
            f"/outlook/migrate-email?email_id=test_email&folder_id={folder_id}"
        )
        assert migrate_response.status_code == 200
        result = migrate_response.json()
        assert result["status"] == "success"
        assert "outlook_id" in result

        # Step 4: Batch migrate multiple emails
        batch_response = test_client.post(
            "/outlook/batch-migrate",
            json=["email1", "email2", "email3"],
            params={"folder_id": folder_id},
        )
        assert batch_response.status_code == 200
        batch_result = batch_response.json()
        assert batch_result["total"] == 3
        assert batch_result["successful"] == 3

        # Verify the correct calls were made
        mock_oauth_flow.get_auth_url.assert_called_once()
        mock_outlook_client.create_folder.assert_called_once()
        mock_outlook_client.migrate_email.assert_called()
        assert mock_gmail_client.get_email.call_count >= 4  # 1 for single + 3 for batch

    @pytest.mark.auth()
    @patch("app.api.routers.outlook.outlook_oauth_flow")
    @patch("app.dependencies.OutlookClient")
    def test_auth_and_folder_management(
        self, mock_client_class, mock_oauth_flow, test_client
    ):
        """Test authentication and folder management."""
        # Set up mocks
        mock_client = MagicMock(spec=OutlookClient)
        mock_client_class.return_value = mock_client
        mock_oauth_flow.get_auth_url.return_value = (
            "https://login.microsoftonline.com/auth"
        )
        mock_oauth_flow.get_token_from_code.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "Mail.Read Mail.ReadWrite",
        }

        # Mock folder operations
        mock_client.get_folders.return_value = [
            {
                "id": "folder1",
                "displayName": "Inbox",
                "parentFolderId": None,
                "childFolderCount": 0,
                "totalItemCount": 10,
                "unreadItemCount": 5,
            }
        ]
        mock_client.create_folder.return_value = {
            "id": "new_folder",
            "displayName": "New Folder",
            "parentFolderId": None,
            "childFolderCount": 0,
            "totalItemCount": 0,
            "unreadItemCount": 0,
        }

        # Step 1: Get auth URL
        auth_url_response = test_client.post("/outlook/auth-url")
        assert auth_url_response.status_code == 200

        # Step 2: Handle auth callback
        callback_response = test_client.post("/outlook/auth-callback?code=test_code")
        assert callback_response.status_code == 200
        token_data = callback_response.json()
        assert token_data["access_token"] == "test_token"

        # Set the Authorization header for subsequent requests
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}

        # Step 3: List folders
        folders_response = test_client.get("/outlook/folders", headers=headers)
        assert folders_response.status_code == 200
        folders = folders_response.json()
        assert len(folders) == 1
        assert folders[0]["display_name"] == "Inbox"

        # Step 4: Create a new folder
        create_folder_response = test_client.post(
            "/outlook/folders?name=New%20Folder", headers=headers
        )
        assert create_folder_response.status_code == 200
        new_folder = create_folder_response.json()
        assert new_folder["display_name"] == "New Folder"

        # Verify the correct calls were made
        mock_oauth_flow.get_auth_url.assert_called_once()
        mock_oauth_flow.get_token_from_code.assert_called_once_with("test_code")
        mock_client.get_folders.assert_called_once()
        mock_client.create_folder.assert_called_once_with("New Folder", None)
