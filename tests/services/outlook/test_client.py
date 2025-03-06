"""Tests for the Outlook client module."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi import HTTPException

from app.services.outlook.client import OutlookClient


@pytest.fixture()
def outlook_client():
    """Fixture for an Outlook client with a mock access token."""
    return OutlookClient("mock_access_token")


@pytest.fixture()
def mock_response():
    """Fixture for a mock response object."""
    mock = MagicMock()
    mock.status_code = 200
    mock.content = json.dumps({"value": []}).encode()
    mock.json.return_value = {"value": []}
    return mock


@pytest.mark.unit()
@pytest.mark.outlook()
class TestOutlookClient:
    """Test suite for the OutlookClient class."""

    def test_init(self, outlook_client):
        """Test client initialization."""
        assert outlook_client.access_token == "mock_access_token"
        assert outlook_client.headers == {
            "Authorization": "Bearer mock_access_token",
            "Content-Type": "application/json",
        }

    @patch("requests.request")
    def test_make_request_success(self, mock_request, outlook_client, mock_response):
        """Test successful API request."""
        mock_request.return_value = mock_response

        result = outlook_client._make_request("GET", "/test-endpoint")

        mock_request.assert_called_once_with(
            "GET",
            "https://graph.microsoft.com/v1.0/test-endpoint",
            params=None,
            json=None,
            headers=outlook_client.headers,
            timeout=30,
        )
        assert result == {"value": []}

    @patch("requests.request")
    def test_make_request_with_params_and_data(self, mock_request, outlook_client, mock_response):
        """Test API request with parameters and data."""
        mock_request.return_value = mock_response

        params = {"$select": "id,subject"}
        data = {"subject": "Test Subject"}

        outlook_client._make_request("POST", "/test-endpoint", params=params, request_data=data)

        mock_request.assert_called_once_with(
            "POST",
            "https://graph.microsoft.com/v1.0/test-endpoint",
            params=params,
            json=data,
            headers=outlook_client.headers,
            timeout=30,
        )

    @patch("requests.request")
    def test_make_request_with_custom_headers(self, mock_request, outlook_client, mock_response):
        """Test API request with custom headers."""
        mock_request.return_value = mock_response

        request_data = {
            "headers": {"Content-Type": "text/plain"},
            "data": "test data",
        }

        outlook_client._make_request("POST", "/test-endpoint", request_data=request_data)

        expected_headers = {
            "Authorization": "Bearer mock_access_token",
            "Content-Type": "text/plain",
        }

        mock_request.assert_called_once_with(
            "POST",
            "https://graph.microsoft.com/v1.0/test-endpoint",
            params=None,
            json={"data": "test data"},
            headers=expected_headers,
            timeout=30,
        )

    @patch("requests.request")
    def test_make_request_error(self, mock_request, outlook_client):
        """Test API request error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.RequestException("API Error")
        mock_request.return_value = mock_response

        with pytest.raises(HTTPException) as excinfo:
            outlook_client._make_request("GET", "/test-endpoint")

        assert excinfo.value.status_code == 400
        assert "API Error" in str(excinfo.value.detail)

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_get_mailbox_info(self, mock_make_request, outlook_client):
        """Test getting mailbox information."""
        mock_make_request.return_value = {"value": ["inbox", "sent items"]}

        result = outlook_client.get_mailbox_info()

        mock_make_request.assert_called_once_with("GET", "/me/mailfolders")
        assert result == {"value": ["inbox", "sent items"]}

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_get_folders(self, mock_make_request, outlook_client):
        """Test getting mail folders."""
        mock_folders = [{"id": "folder1", "displayName": "Inbox"}]
        mock_make_request.return_value = {"value": mock_folders}

        result = outlook_client.get_folders()

        mock_make_request.assert_called_once_with("GET", "/me/mailfolders?$top=100&$expand=childFolders")
        assert result == mock_folders

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_create_folder_root(self, mock_make_request, outlook_client):
        """Test creating a folder at the root level."""
        mock_folder = {"id": "new_folder", "displayName": "Test Folder"}
        mock_make_request.return_value = mock_folder

        result = outlook_client.create_folder("Test Folder")

        mock_make_request.assert_called_once_with(
            "POST", "/me/mailfolders", request_data={"displayName": "Test Folder"}
        )
        assert result == mock_folder

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_create_folder_with_parent(self, mock_make_request, outlook_client):
        """Test creating a subfolder."""
        mock_folder = {"id": "new_subfolder", "displayName": "Test Subfolder"}
        mock_make_request.return_value = mock_folder

        result = outlook_client.create_folder("Test Subfolder", parent_folder_id="parent_id")

        mock_make_request.assert_called_once_with(
            "POST",
            "/me/mailfolders/parent_id/childFolders",
            request_data={"displayName": "Test Subfolder"},
        )
        assert result == mock_folder

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_get_messages_default(self, mock_make_request, outlook_client):
        """Test getting messages with default parameters."""
        mock_messages = [{"id": "msg1", "subject": "Test Email"}]
        mock_make_request.return_value = {"value": mock_messages}

        messages, skip_token = outlook_client.get_messages()

        mock_make_request.assert_called_once()
        assert messages == mock_messages
        assert skip_token is None

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_get_messages_with_folder_and_query(self, mock_make_request, outlook_client):
        """Test getting messages with folder ID and search query."""
        mock_messages = [{"id": "msg1", "subject": "Test Email"}]
        mock_make_request.return_value = {
            "value": mock_messages,
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages?$skiptoken=token123&$top=50",
        }

        messages, skip_token = outlook_client.get_messages(folder_id="folder_id", query="important", top=10, skip=5)

        expected_params = {
            "$top": 10,
            "$skip": 5,
            "$select": ("id,conversationId,subject,bodyPreview,receivedDateTime," "from,toRecipients,hasAttachments"),
            "$orderby": "receivedDateTime desc",
            "$search": "important",
        }

        mock_make_request.assert_called_once_with("GET", "/me/mailfolders/folder_id/messages", params=expected_params)
        assert messages == mock_messages
        assert skip_token == "token123"

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_get_message(self, mock_make_request, outlook_client):
        """Test getting a specific message."""
        mock_message = {"id": "msg1", "subject": "Test Email"}
        mock_make_request.return_value = mock_message

        result = outlook_client.get_message("msg1")

        mock_make_request.assert_called_once_with("GET", "/me/messages/msg1?$expand=attachments")
        assert result == mock_message

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_get_attachment(self, mock_make_request, outlook_client):
        """Test getting a specific attachment."""
        mock_attachment = {"id": "att1", "name": "test.pdf"}
        mock_make_request.return_value = mock_attachment

        result = outlook_client.get_attachment("msg1", "att1")

        mock_make_request.assert_called_once_with("GET", "/me/messages/msg1/attachments/att1")
        assert result == mock_attachment

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_create_message_simple(self, mock_make_request, outlook_client):
        """Test creating a simple message."""
        mock_message = {"id": "new_msg", "subject": "Test Subject"}
        mock_make_request.return_value = mock_message

        result = outlook_client.create_message(
            subject="Test Subject",
            body="Test Body",
            to_recipients=["test@example.com"],
        )

        expected_data = {
            "subject": "Test Subject",
            "body": {
                "contentType": "html",
                "content": "Test Body",
            },
            "toRecipients": [{"emailAddress": {"address": "test@example.com"}}],
        }

        mock_make_request.assert_called_once_with("POST", "/me/messages", request_data=expected_data)
        assert result == mock_message

    @patch("app.services.outlook.client.OutlookClient._make_request")
    @patch("app.services.outlook.client.OutlookClient.add_attachment")
    def test_create_message_with_attachments(self, mock_add_attachment, mock_make_request, outlook_client):
        """Test creating a message with attachments."""
        mock_message = {"id": "new_msg", "subject": "Test Subject"}
        mock_make_request.return_value = mock_message

        attachments = [
            {
                "name": "test.pdf",
                "content": b"test content",
                "contentType": "application/pdf",
            }
        ]

        result = outlook_client.create_message(
            subject="Test Subject",
            body="Test Body",
            to_recipients=["test@example.com"],
            attachments=attachments,
        )

        mock_make_request.assert_called_once()
        mock_add_attachment.assert_called_once_with(
            message_id="new_msg",
            attachment_name="test.pdf",
            content_bytes=b"test content",
            content_type="application/pdf",
        )
        assert result == mock_message

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_add_attachment(self, mock_make_request, outlook_client):
        """Test adding an attachment to a message."""
        mock_attachment = {"id": "att1", "name": "test.pdf"}
        mock_make_request.return_value = mock_attachment

        content_bytes = b"test content"
        encoded_content = base64.b64encode(content_bytes).decode("utf-8")

        result = outlook_client.add_attachment(
            message_id="msg1",
            attachment_name="test.pdf",
            content_bytes=content_bytes,
            content_type="application/pdf",
        )

        expected_data = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": "test.pdf",
            "contentType": "application/pdf",
            "contentBytes": encoded_content,
        }

        mock_make_request.assert_called_once_with("POST", "/me/messages/msg1/attachments", request_data=expected_data)
        assert result == mock_attachment

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_add_attachment_guess_content_type(self, mock_make_request, outlook_client):
        """Test adding an attachment with content type guessing."""
        mock_attachment = {"id": "att1", "name": "test.pdf"}
        mock_make_request.return_value = mock_attachment

        content_bytes = b"test content"

        with patch("mimetypes.guess_type", return_value=("application/pdf", None)):
            result = outlook_client.add_attachment(
                message_id="msg1",
                attachment_name="test.pdf",
                content_bytes=content_bytes,
            )

        mock_make_request.assert_called_once()
        assert result == mock_attachment

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_send_message(self, mock_make_request, outlook_client):
        """Test sending a message."""
        mock_response = {"status": "sent"}
        mock_make_request.return_value = mock_response

        result = outlook_client.send_message("msg1")

        mock_make_request.assert_called_once_with("POST", "/me/messages/msg1/send")
        assert result == mock_response

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_import_email_default_folder(self, mock_make_request, outlook_client):
        """Test importing an email to the default folder."""
        mock_response = {"id": "imported_msg"}
        mock_make_request.return_value = mock_response

        mime_content = "MIME-Version: 1.0\nSubject: Test\n\nBody"

        result = outlook_client.import_email(mime_content)

        expected_request_data = {
            "headers": {"Content-Type": "text/plain"},
            "data": mime_content,
        }

        mock_make_request.assert_called_once_with("POST", "/me/messages/$value", request_data=expected_request_data)
        assert result == mock_response

    @patch("app.services.outlook.client.OutlookClient._make_request")
    def test_import_email_specific_folder(self, mock_make_request, outlook_client):
        """Test importing an email to a specific folder."""
        mock_response = {"id": "imported_msg"}
        mock_make_request.return_value = mock_response

        mime_content = "MIME-Version: 1.0\nSubject: Test\n\nBody"

        result = outlook_client.import_email(mime_content, folder_id="folder1")

        expected_request_data = {
            "headers": {"Content-Type": "text/plain"},
            "data": mime_content,
        }

        mock_make_request.assert_called_once_with(
            "POST",
            "/me/mailfolders/folder1/messages/$value",
            request_data=expected_request_data,
        )
        assert result == mock_response

    @patch("app.services.outlook.client.OutlookClient.create_message")
    @patch("app.services.outlook.client.OutlookClient.add_attachment")
    def test_migrate_email(self, mock_add_attachment, mock_create_message, outlook_client):
        """Test migrating an email from Gmail to Outlook."""
        mock_message = {"id": "migrated_msg", "subject": "Test Subject"}
        mock_create_message.return_value = mock_message

        gmail_message = {
            "subject": "Test Subject",
            "body": "<html><body>Test Body</body></html>",
            "to_address": "recipient@example.com",
        }

        attachments = [
            {
                "name": "test.pdf",
                "content": b"test content",
                "contentType": "application/pdf",
            }
        ]

        result = outlook_client.migrate_email(
            gmail_message=gmail_message,
            attachments=attachments,
            folder_id="folder1",
        )

        mock_create_message.assert_called_once_with(
            subject="Test Subject",
            body="<html><body>Test Body</body></html>",
            to_recipients=["recipient@example.com"],
            is_html=True,
            folder_id="folder1",
        )

        mock_add_attachment.assert_called_once_with(
            message_id="migrated_msg",
            attachment_name="test.pdf",
            content_bytes=b"test content",
            content_type="application/pdf",
        )

        assert result == mock_message
