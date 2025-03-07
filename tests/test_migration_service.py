"""Tests for the Gmail to Outlook migration service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.gmail.client import GmailClient
from app.services.migration.gmail_to_outlook import GmailToOutlookMigrationService
from app.services.outlook.client import OutlookClient


@pytest.fixture()
def gmail_client():
    """Create a mock Gmail client."""
    client = MagicMock(spec=GmailClient)
    client.service = MagicMock()
    return client


@pytest.fixture()
def outlook_client():
    """Create a mock Outlook client."""
    client = MagicMock(spec=OutlookClient)
    return client


@pytest.fixture()
def migration_service(gmail_client, outlook_client):
    """Create a migration service with mock clients."""
    with patch(
        "app.services.migration.gmail_to_outlook.GmailLabelsService"
    ) as mock_labels_service_class:
        # Create a mock instance of GmailLabelsService
        mock_labels_service = MagicMock()
        # Configure the class to return our mock instance
        mock_labels_service_class.return_value = mock_labels_service

        # Create the service
        service = GmailToOutlookMigrationService(gmail_client, outlook_client)

        # Verify that our mock was used
        assert service.labels_service == mock_labels_service

        return service


class TestGmailToOutlookMigrationService:
    """Tests for the Gmail to Outlook migration service."""

    @pytest.mark.asyncio()
    async def test_migrate_labels_to_folders(self, migration_service):
        """Test migrating Gmail labels to Outlook folders."""
        # Setup mock data
        gmail_labels = [
            {"id": "label1", "name": "Label 1", "type": "user"},
            {"id": "label2", "name": "Label 2", "type": "user"},
            {"id": "INBOX", "name": "INBOX", "type": "system"},
        ]
        outlook_folders = [
            {"id": "folder1", "displayName": "Inbox"},
            {"id": "folder2", "displayName": "Sent Items"},
        ]

        # Configure mocks
        migration_service.labels_service.get_all_labels.return_value = gmail_labels
        migration_service.outlook_client.get_folders.return_value = outlook_folders
        migration_service.outlook_client.create_folder.side_effect = [
            {"id": "new_folder1", "displayName": "Label 1"},
            {"id": "new_folder2", "displayName": "Label 2"},
        ]

        # Call the method
        result = await migration_service.migrate_labels_to_folders()

        # Verify results
        assert len(result) == 3
        assert result["label1"] == "new_folder1"
        assert result["label2"] == "new_folder2"
        assert result["INBOX"] == "folder1"

        # Verify the correct methods were called
        migration_service.labels_service.get_all_labels.assert_called_once()
        migration_service.outlook_client.get_folders.assert_called_once()
        assert migration_service.outlook_client.create_folder.call_count == 2

    @pytest.mark.asyncio()
    async def test_migrate_emails_by_label(self, migration_service):
        """Test migrating emails by label."""
        # Setup mock data
        label_id = "label1"
        folder_id = "folder1"
        emails = [
            {"id": "email1", "threadId": "thread1"},
            {"id": "email2", "threadId": "thread2"},
        ]

        # Configure mocks
        migration_service.folder_mapping = {label_id: folder_id}
        migration_service.gmail_client.get_emails_with_labels.return_value = emails
        migration_service.gmail_client.get_email_content.side_effect = [
            {"subject": "Email 1", "body": "Body 1", "has_attachments": False},
            {
                "subject": "Email 2",
                "body": "Body 2",
                "has_attachments": True,
                "attachments": [
                    {"id": "att1", "filename": "file.txt", "mime_type": "text/plain"}
                ],
            },
        ]
        migration_service.gmail_client.get_attachment.return_value = (
            b"attachment content"
        )

        # Call the method
        result = await migration_service.migrate_emails_by_label(label_id, max_emails=2)

        # Verify results
        assert result["total"] == 2
        assert result["successful"] == 2
        assert result["failed"] == 0
        assert len(result["failed_ids"]) == 0

        # Verify the correct methods were called
        migration_service.gmail_client.get_emails_with_labels.assert_called_once_with(
            label_ids=[label_id], max_results=2
        )
        assert migration_service.gmail_client.get_email_content.call_count == 2
        migration_service.gmail_client.get_attachment.assert_called_once()
        assert migration_service.outlook_client.migrate_email.call_count == 2

    @pytest.mark.asyncio()
    async def test_migrate_emails_by_label_with_error(self, migration_service):
        """Test migrating emails by label with an error."""
        # Setup mock data
        label_id = "label1"
        folder_id = "folder1"
        emails = [
            {"id": "email1", "threadId": "thread1"},
            {"id": "email2", "threadId": "thread2"},
        ]

        # Configure mocks
        migration_service.folder_mapping = {label_id: folder_id}
        migration_service.gmail_client.get_emails_with_labels.return_value = emails
        migration_service.gmail_client.get_email_content.side_effect = [
            {"subject": "Email 1", "body": "Body 1", "has_attachments": False},
            Exception("Error getting email content"),
        ]

        # Call the method
        result = await migration_service.migrate_emails_by_label(label_id, max_emails=2)

        # Verify results
        assert result["total"] == 2
        assert result["successful"] == 1
        assert result["failed"] == 1
        assert len(result["failed_ids"]) == 1
        assert "email2" in result["failed_ids"]

    @pytest.mark.asyncio()
    async def test_migrate_all_emails(self, migration_service):
        """Test migrating all emails."""
        # Setup mock data
        gmail_labels = [
            {"id": "label1", "name": "Label 1", "type": "user"},
            {"id": "label2", "name": "Label 2", "type": "user"},
        ]

        # Configure mocks
        migration_service.labels_service.get_all_labels.return_value = gmail_labels

        # Mock the migrate_labels_to_folders method
        migration_service.migrate_labels_to_folders = AsyncMock()
        migration_service.migrate_labels_to_folders.return_value = {
            "label1": "folder1",
            "label2": "folder2",
        }

        # Mock the migrate_emails_by_label method
        migration_service.migrate_emails_by_label = AsyncMock()
        migration_service.migrate_emails_by_label.side_effect = [
            {"total": 5, "successful": 4, "failed": 1, "failed_ids": ["email3"]},
            {"total": 3, "successful": 3, "failed": 0, "failed_ids": []},
        ]

        # Call the method
        result = await migration_service.migrate_all_emails(max_emails_per_label=10)

        # Verify results
        assert result["total_labels"] == 2
        assert result["processed_labels"] == 2
        assert result["total_emails"] == 8
        assert result["successful_emails"] == 7
        assert result["failed_emails"] == 1
        assert "Label 1" in result["label_results"]
        assert "Label 2" in result["label_results"]

        # Verify the correct methods were called
        migration_service.migrate_labels_to_folders.assert_called_once()
        assert migration_service.migrate_emails_by_label.call_count == 2
        migration_service.migrate_emails_by_label.assert_any_call(
            "label1", max_emails=10
        )
        migration_service.migrate_emails_by_label.assert_any_call(
            "label2", max_emails=10
        )
