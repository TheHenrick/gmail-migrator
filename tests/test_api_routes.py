"""
Tests for the API routes.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from app.app import create_app


@pytest.fixture
def client():
    """Fixture for Flask test client."""
    app = create_app(testing=True)
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_oauth_flow():
    """Fixture for mock OAuth flow."""
    with patch('app.api.routers.gmail.oauth_flow') as mock_flow:
        mock_flow.get_authorization_url.return_value = 'https://mock-auth-url.com', 'mock_state'
        yield mock_flow


@pytest.fixture
def mock_gmail_client():
    """Fixture for mock Gmail client."""
    with patch('app.api.routers.gmail.GmailClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Set up mock responses
        mock_client.get_email_list.return_value = {
            'messages': [{'id': 'msg1'}, {'id': 'msg2'}],
            'next_page_token': 'token123'
        }
        
        mock_client.get_email.return_value = {
            'id': 'msg1',
            'subject': 'Test Subject',
            'from': 'sender@example.com',
            'body_text': 'Test body'
        }
        
        yield mock_client


def test_auth_url(client, mock_oauth_flow):
    """Test getting OAuth authorization URL."""
    response = client.get('/api/gmail/auth-url')
    data = json.loads(response.data)
    
    assert response.status_code == 200
    assert 'auth_url' in data
    assert data['auth_url'] == 'https://mock-auth-url.com'
    mock_oauth_flow.get_authorization_url.assert_called_once()


def test_auth_callback(client, mock_oauth_flow):
    """Test OAuth callback handling."""
    mock_oauth_flow.exchange_code.return_value = {'token': 'mock_token'}
    
    # Set up the session before making the request
    with client.session_transaction() as session:
        session['oauth_state'] = 'mock_state'
    
    response = client.get('/api/gmail/auth-callback?code=test_code&state=mock_state')
    data = json.loads(response.data)
    
    assert response.status_code == 200
    assert 'message' in data
    mock_oauth_flow.exchange_code.assert_called_once_with('test_code')


def test_get_emails(client, mock_gmail_client):
    """Test getting emails from Gmail."""
    with patch('app.api.routers.gmail.get_session_credentials', return_value={'token': 'mock_token'}):
        response = client.get('/api/gmail/emails?query=test&max_results=10')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert 'messages' in data
        assert len(data['messages']) == 2
        mock_gmail_client.get_email_list.assert_called_once_with(
            query='test', 
            max_results=10,
            page_token=None
        )


def test_get_email_detail(client, mock_gmail_client):
    """Test getting email details from Gmail."""
    with patch('app.api.routers.gmail.get_session_credentials', return_value={'token': 'mock_token'}):
        response = client.get('/api/gmail/emails/msg1')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['id'] == 'msg1'
        assert data['subject'] == 'Test Subject'
        mock_gmail_client.get_email.assert_called_once_with('msg1')


def test_unauthorized_access(client):
    """Test unauthorized access to protected endpoints."""
    with patch('app.api.routers.gmail.get_session_credentials', return_value=None):
        response = client.get('/api/gmail/emails')
        data = json.loads(response.data)
        
        assert response.status_code == 401
        assert 'error' in data 