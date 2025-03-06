"""Common test fixtures for the application."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.outlook.auth import OutlookAuthManager
from app.services.outlook.client import OutlookClient


@pytest.fixture()
def mock_outlook_auth_manager():
    """Fixture for a mock Outlook auth manager."""
    patch("app.services.outlook.auth.msal.ConfidentialClientApplication").start()
    manager = OutlookAuthManager(
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8000/test-callback",
    )

    manager.get_auth_url = MagicMock(return_value="https://test-auth-url")
    manager.get_token_from_code = MagicMock(
        return_value={
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
        }
    )
    manager.refresh_token = MagicMock(
        return_value={"access_token": "refreshed_access_token"}
    )

    yield manager
    patch.stopall()


@pytest.fixture()
def mock_outlook_client():
    """Fixture for a mock Outlook client."""
    client = MagicMock(spec=OutlookClient)
    client.get_folders.return_value = [
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
    client.create_folder.return_value = {
        "id": "new_folder",
        "displayName": "Test Folder",
        "parentFolderId": None,
        "childFolderCount": 0,
        "totalItemCount": 0,
        "unreadItemCount": 0,
    }
    client.get_messages.return_value = (
        [
            {
                "id": "msg1",
                "subject": "Test Email",
                "bodyPreview": "This is a test email",
                "from": {"emailAddress": {"address": "sender@example.com"}},
                "toRecipients": [
                    {"emailAddress": {"address": "recipient@example.com"}}
                ],
                "receivedDateTime": "2023-01-01T12:00:00Z",
                "hasAttachments": False,
            }
        ],
        None,
    )
    client.get_message.return_value = {
        "id": "msg1",
        "subject": "Test Email",
        "body": {"content": "<p>This is a test email</p>", "contentType": "html"},
        "from": {"emailAddress": {"address": "sender@example.com"}},
        "toRecipients": [{"emailAddress": {"address": "recipient@example.com"}}],
        "receivedDateTime": "2023-01-01T12:00:00Z",
        "hasAttachments": False,
        "attachments": [],
    }
    client.migrate_email.return_value = {
        "id": "migrated_msg",
        "subject": "Migrated Email",
    }
    return client


@pytest.fixture()
def mock_gmail_client():
    """Fixture for a mock Gmail client."""
    client = MagicMock()
    client.get_email.return_value = {
        "id": "gmail_msg1",
        "subject": "Test Gmail Email",
        "body": "<p>This is a test email from Gmail</p>",
        "to_address": "recipient@example.com",
        "has_attachments": False,
        "attachments": [],
    }
    client.get_attachment.return_value = {
        "id": "att1",
        "filename": "test.pdf",
        "data": b"test content",
        "mime_type": "application/pdf",
    }
    return client
