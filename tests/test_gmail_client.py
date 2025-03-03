"""Tests for the GmailClient class."""

import base64
import json
import os
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from app.services.gmail.client import GmailClient
from app.services.gmail.labels import GmailLabelsService

# Constants for test data
TEST_CREDENTIALS_FILE = "tests/test_credentials.json"
MAX_TEST_RESULTS = 10
TEST_EMAIL_ID = "test_email_id"
TEST_ATTACHMENT_ID = "test_attachment_id"


@pytest.fixture()
def mock_gmail_service() -> MagicMock:
    """
    Create a mock Gmail service.

    Returns:
        MagicMock: A mock Gmail API service
    """
    mock_service = MagicMock()
    return mock_service


@pytest.fixture()
def gmail_client(mock_gmail_service: MagicMock) -> GmailClient:
    """
    Create a GmailClient with a mock service.

    Args:
        mock_gmail_service: The mock Gmail service to use

    Returns:
        GmailClient: A client instance with mocked service
    """
    client = GmailClient()
    client.service = mock_gmail_service
    return client


@pytest.fixture()
def test_credentials_file() -> Generator[str, None, None]:
    """
    Create a temporary credentials file for testing.

    Yields:
        str: Path to the test credentials file
    """
    # Create test credentials file
    credentials = {
        "installed": {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "redirect_uris": ["http://localhost"],
        }
    }

    os.makedirs(os.path.dirname(TEST_CREDENTIALS_FILE), exist_ok=True)
    with open(TEST_CREDENTIALS_FILE, "w") as f:
        json.dump(credentials, f)

    yield TEST_CREDENTIALS_FILE

    # Cleanup
    if os.path.exists(TEST_CREDENTIALS_FILE):
        os.remove(TEST_CREDENTIALS_FILE)


def test_init() -> None:
    """Test GmailClient initialization."""
    client = GmailClient()
    assert client.service is None


@patch("app.services.gmail.client.build")
@patch("app.services.gmail.client.InstalledAppFlow")
def test_authenticate(
    mock_installed_app_flow: MagicMock,
    mock_build: MagicMock,
    test_credentials_file: str,
) -> None:
    """Test authentication process."""
    # Setup
    mock_flow = MagicMock()
    mock_installed_app_flow.from_client_secrets_file.return_value = mock_flow

    mock_credentials = MagicMock()
    mock_credentials.token = "test_token"
    mock_credentials.refresh_token = "test_refresh_token"
    mock_credentials.token_uri = "test_token_uri"
    mock_credentials.client_id = "test_client_id"
    mock_credentials.client_secret = "test_client_secret"
    mock_credentials.scopes = ["https://mail.google.com/"]

    mock_flow.run_local_server.return_value = mock_credentials

    # Execute
    client = GmailClient(credentials_path=test_credentials_file)
    result = client.authenticate()

    # Verify
    mock_installed_app_flow.from_client_secrets_file.assert_called_once_with(
        test_credentials_file,
        [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.labels",
        ],
    )
    mock_flow.run_local_server.assert_called_once_with(port=0)

    assert result["token"] == "test_token"
    assert result["refresh_token"] == "test_refresh_token"
    assert result["token_uri"] == "test_token_uri"
    assert result["client_id"] == "test_client_id"
    assert result["client_secret"] == "test_client_secret"
    assert result["scopes"] == ["https://mail.google.com/"]


def test_get_email_list(
    gmail_client: GmailClient, mock_gmail_service: MagicMock
) -> None:
    """Test fetching email list."""
    # Setup
    mock_messages_resource = mock_gmail_service.users.return_value.messages
    mock_list = mock_messages_resource.return_value.list
    mock_list.return_value.execute.return_value = {
        "messages": [{"id": "msg1"}, {"id": "msg2"}],
        "nextPageToken": "next_token",
    }

    # Execute
    result = gmail_client.get_email_list(
        query="test query", max_results=MAX_TEST_RESULTS, page_token="page_token"
    )

    # Verify
    mock_list.assert_called_with(
        userId="me", q="test query", maxResults=MAX_TEST_RESULTS, pageToken="page_token"
    )
    assert result["messages"][0]["id"] == "msg1"
    assert result["messages"][1]["id"] == "msg2"
    assert result["next_page_token"] == "next_token"


def test_get_email_content(
    gmail_client: GmailClient, mock_gmail_service: MagicMock
) -> None:
    """Test fetching email content."""
    # Setup
    mock_messages_resource = mock_gmail_service.users.return_value.messages
    mock_get = mock_messages_resource.return_value.get
    mock_get.return_value.execute.return_value = {
        "id": TEST_EMAIL_ID,
        "threadId": "thread1",
        "labelIds": ["INBOX"],
        "snippet": "Email snippet",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Test Subject"},
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Date", "value": "Mon, 1 Jan 2023 12:00:00 +0000"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": base64.b64encode(b"Email body").decode()},
                },
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": base64.b64encode(b"<html>Email body</html>").decode()
                    },
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "test.pdf",
                    "body": {"attachmentId": TEST_ATTACHMENT_ID},
                },
            ],
        },
    }

    # Execute
    result = gmail_client.get_email_content(TEST_EMAIL_ID)

    # Verify
    mock_get.assert_called_with(userId="me", id=TEST_EMAIL_ID)
    assert result["id"] == TEST_EMAIL_ID
    assert result["subject"] == "Test Subject"
    assert result["from"] == "sender@example.com"
    assert result["to"] == "recipient@example.com"
    assert result["date"] == "Mon, 1 Jan 2023 12:00:00 +0000"
    assert "body" in result
    assert result["body"]["plain"] == "Email body"
    assert result["body"]["html"] == "<html>Email body</html>"
    assert len(result["attachments"]) == 1
    assert result["attachments"][0]["filename"] == "test.pdf"
    assert result["attachments"][0]["mimeType"] == "application/pdf"
    assert result["attachments"][0]["id"] == TEST_ATTACHMENT_ID


def test_get_attachment(
    gmail_client: GmailClient, mock_gmail_service: MagicMock
) -> None:
    """Test fetching an attachment."""
    # Setup
    mock_attachments_resource = (
        mock_gmail_service.users.return_value.messages.return_value.attachments
    )
    mock_get = mock_attachments_resource.return_value.get
    mock_get.return_value.execute.return_value = {
        "data": base64.b64encode(b"attachment data").decode(),
    }

    # Execute
    result = gmail_client.get_attachment(TEST_EMAIL_ID, TEST_ATTACHMENT_ID)

    # Verify
    mock_get.assert_called_with(
        userId="me", messageId=TEST_EMAIL_ID, id=TEST_ATTACHMENT_ID
    )
    assert result == b"attachment data"


@pytest.fixture()
def mock_credentials():
    """Fixture for mock credentials."""
    return {
        "token": "ya29.mock_token",
        "refresh_token": "1//mock_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "mock_client_id.apps.googleusercontent.com",
        "client_secret": "mock_client_secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        "expiry": "2023-04-01T12:00:00.000Z",
    }


@pytest.fixture()
def mock_message():
    """Fixture for a mock Gmail message."""
    return {
        "id": "12345",
        "threadId": "12345",
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": "This is a test email",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "Test Sender <sender@example.com>"},
                {"name": "To", "value": "Test Recipient <recipient@example.com>"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Mon, 1 Apr 2023 12:00:00 +0000"},
            ],
            "parts": [
                {
                    "partId": "0",
                    "mimeType": "text/plain",
                    "body": {
                        "data": base64.b64encode(b"This is a test email").decode()
                    },
                },
                {
                    "partId": "1",
                    "mimeType": "text/html",
                    "body": {
                        "data": base64.b64encode(
                            b"<div>This is a test email</div>"
                        ).decode()
                    },
                },
                {
                    "partId": "2",
                    "mimeType": "application/pdf",
                    "filename": "test.pdf",
                    "body": {"attachmentId": "attachment123"},
                },
            ],
        },
    }


@pytest.fixture()
def mock_labels():
    """Fixture for mock Gmail labels."""
    return {
        "labels": [
            {
                "id": "INBOX",
                "name": "INBOX",
                "type": "system",
                "messagesTotal": 100,
                "messagesUnread": 10,
            },
            {
                "id": "SENT",
                "name": "SENT",
                "type": "system",
                "messagesTotal": 50,
                "messagesUnread": 0,
            },
            {
                "id": "IMPORTANT",
                "name": "IMPORTANT",
                "type": "system",
                "messagesTotal": 30,
                "messagesUnread": 5,
            },
            {
                "id": "user-label-1",
                "name": "Work",
                "type": "user",
                "messagesTotal": 20,
                "messagesUnread": 2,
            },
            {
                "id": "user-label-2",
                "name": "Family/Personal",
                "type": "user",
                "messagesTotal": 15,
                "messagesUnread": 0,
            },
        ]
    }


def test_build_service(gmail_client):
    """Test building the Gmail API service."""
    # Set credentials to avoid ValueError
    gmail_client.credentials = {
        "token": "test_token",
        "refresh_token": "test_refresh_token",
        "token_uri": "test_token_uri",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
    }

    with patch("app.services.gmail.client.build") as mock_build:
        gmail_client._build_service()
        mock_build.assert_called_once()


def test_parse_email_content(gmail_client, mock_message):
    """Test parsing email content from Gmail API format."""
    result = gmail_client.parse_email_content(mock_message)

    # Basic assertions
    assert result["id"] == "12345"
    assert result["thread_id"] == "12345"
    assert "body" in result
    assert result["body"]["plain"] == "This is a test email"
    assert result["body"]["html"] == "<div>This is a test email</div>"
    assert len(result["attachments"]) == 1
    assert result["attachments"][0]["filename"] == "test.pdf"


def test_get_all_labels(gmail_client, mock_labels):
    """Test fetching all Gmail labels."""
    # Set up the mock
    mock_response = MagicMock()
    mock_response.execute.return_value = mock_labels
    gmail_client.service.users().labels().list.return_value = mock_response

    # Create the labels service
    labels_service = GmailLabelsService(gmail_client)

    # Call the method
    result = labels_service.get_all_labels()

    # Verify results
    assert len(result) == 5
    assert result[0]["id"] == "INBOX"
    assert result[1]["id"] == "SENT"
    assert result[3]["id"] == "user-label-1"
