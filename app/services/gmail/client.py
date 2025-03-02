"""
Gmail API client for authentication and fetching emails.
"""
import logging
from typing import List, Dict, Any, Optional

import google.oauth2.credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings

logger = logging.getLogger(__name__)

# Define the scopes required by Gmail API
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailClient:
    """Client for interfacing with the Gmail API."""
    
    def __init__(self, credentials: Optional[Dict[str, Any]] = None):
        """
        Initialize the Gmail client.
        
        Args:
            credentials: OAuth2 credentials for Gmail API access
        """
        self.credentials = credentials
        self.service = None
    
    def authenticate(self) -> Dict[str, Any]:
        """
        Authenticate with Gmail API using OAuth2.
        
        Returns:
            Dictionary containing OAuth credentials
        """
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": settings.GMAIL_CLIENT_ID,
                    "client_secret": settings.GMAIL_CLIENT_SECRET,
                    "redirect_uris": [settings.GMAIL_REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            SCOPES
        )
        
        # Run the local server flow
        credentials = flow.run_local_server(port=8080)
        self.credentials = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Build the service
        self._build_service()
        
        return self.credentials
    
    def _build_service(self):
        """Build the Gmail API service."""
        if not self.credentials:
            raise ValueError("No credentials available. Please authenticate first.")
        
        credentials = google.oauth2.credentials.Credentials(
            token=self.credentials.get('token'),
            refresh_token=self.credentials.get('refresh_token'),
            token_uri=self.credentials.get('token_uri'),
            client_id=self.credentials.get('client_id'),
            client_secret=self.credentials.get('client_secret'),
            scopes=self.credentials.get('scopes')
        )
        
        self.service = build('gmail', 'v1', credentials=credentials)
    
    def get_email_list(self, query: str = '', max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Get a list of emails matching the query.
        
        Args:
            query: Gmail search query
            max_results: Maximum number of results to return
            
        Returns:
            List of email metadata
        """
        if not self.service:
            self._build_service()
        
        try:
            results = self.service.users().messages().list(
                userId='me', 
                q=query, 
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            return messages
        except HttpError as error:
            logger.error(f"Error fetching emails: {error}")
            return []
    
    def get_email_content(self, message_id: str) -> Dict[str, Any]:
        """
        Get the full content of an email by its ID.
        
        Args:
            message_id: The Gmail message ID
            
        Returns:
            Dictionary containing email content
        """
        if not self.service:
            self._build_service()
        
        try:
            message = self.service.users().messages().get(
                userId='me', 
                id=message_id,
                format='full'
            ).execute()
            
            return message
        except HttpError as error:
            logger.error(f"Error fetching email content: {error}")
            return {} 