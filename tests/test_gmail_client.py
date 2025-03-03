"""
Tests for the Gmail client.
"""
import pytest
import json
from unittest.mock import MagicMock, patch

from app.services.gmail.client import GmailClient
from app.services.gmail.labels import GmailLabelsService


@pytest.fixture
def mock_credentials():
    """Fixture for mock credentials."""
    return {
        'token': 'mock_token',
        'refresh_token': 'mock_refresh_token',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'client_id': 'mock_client_id',
        'client_secret': 'mock_secret',
        'scopes': ['https://www.googleapis.com/auth/gmail.readonly']
    }


@pytest.fixture
def gmail_client(mock_credentials):
    """Fixture for Gmail client with mock credentials."""
    client = GmailClient(mock_credentials)
    # Mock the service
    client.service = MagicMock()
    return client


@pytest.fixture
def mock_message():
    """Fixture for a mock Gmail message."""
    return {
        'id': 'mock_message_id',
        'threadId': 'mock_thread_id',
        'labelIds': ['INBOX', 'UNREAD'],
        'snippet': 'This is a test email',
        'payload': {
            'headers': [
                {'name': 'Subject', 'value': 'Test Subject'},
                {'name': 'From', 'value': 'sender@example.com'},
                {'name': 'To', 'value': 'recipient@example.com'},
                {'name': 'Date', 'value': 'Mon, 1 Jan 2023 12:00:00 +0000'}
            ],
            'mimeType': 'multipart/alternative',
            'parts': [
                {
                    'mimeType': 'text/plain',
                    'body': {
                        'data': 'VGhpcyBpcyBhIHRlc3QgZW1haWwgYm9keQ=='  # "This is a test email body"
                    }
                },
                {
                    'mimeType': 'text/html',
                    'body': {
                        'data': 'PGRpdj5UaGlzIGlzIGEgdGVzdCBlbWFpbCBib2R5PC9kaXY+'  # "<div>This is a test email body</div>"
                    }
                }
            ]
        }
    }


@pytest.fixture
def mock_labels():
    """Fixture for mock Gmail labels."""
    return [
        {
            'id': 'INBOX',
            'name': 'INBOX',
            'type': 'system',
            'messagesTotal': 42
        },
        {
            'id': 'SENT',
            'name': 'SENT',
            'type': 'system',
            'messagesTotal': 21
        },
        {
            'id': 'Label_123',
            'name': 'Work',
            'type': 'user',
            'messagesTotal': 10
        }
    ]


def test_build_service(gmail_client):
    """Test building the Gmail API service."""
    with patch('app.services.gmail.client.build') as mock_build:
        gmail_client.service = None
        gmail_client._build_service()
        mock_build.assert_called_once()


def test_get_email_list(gmail_client):
    """Test getting a list of emails."""
    mock_response = {
        'messages': [{'id': 'msg1'}, {'id': 'msg2'}],
        'nextPageToken': 'token123'
    }
    
    # Mock the messages.list().execute() chain
    messages_list = MagicMock()
    messages_list.execute.return_value = mock_response
    gmail_client.service.users().messages().list.return_value = messages_list
    
    # Call method
    result = gmail_client.get_email_list(query='test', max_results=10)
    
    # Verify results
    assert result['messages'] == mock_response['messages']
    assert result['next_page_token'] == mock_response['nextPageToken']
    
    # Verify the API was called correctly
    gmail_client.service.users().messages().list.assert_called_once()


def test_parse_email_content(gmail_client, mock_message):
    """Test parsing Gmail message content."""
    email_data = gmail_client.parse_email_content(mock_message)
    
    assert email_data['id'] == 'mock_message_id'
    assert email_data['thread_id'] == 'mock_thread_id'
    assert email_data['subject'] == 'Test Subject'
    assert email_data['from'] == 'sender@example.com'
    assert email_data['to'] == 'recipient@example.com'
    assert 'This is a test email body' in email_data['body_text']
    assert '<div>This is a test email body</div>' in email_data['body_html']


def test_get_all_labels(gmail_client, mock_labels):
    """Test getting all Gmail labels."""
    # Create labels service
    labels_service = GmailLabelsService(gmail_client)
    
    # Mock the labels.list().execute() chain
    labels_list = MagicMock()
    labels_list.execute.return_value = {'labels': mock_labels}
    gmail_client.service.users().labels().list.return_value = labels_list
    
    # Call method
    result = labels_service.get_all_labels()
    
    # Verify results
    assert len(result) == 3
    assert result[0]['id'] == 'INBOX'
    assert result[1]['id'] == 'SENT'
    assert result[2]['id'] == 'Label_123'
    
    # Verify API was called correctly
    gmail_client.service.users().labels().list.assert_called_once_with(userId='me') 