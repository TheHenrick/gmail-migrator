"""
Gmail API client for authentication and fetching emails.
"""
import logging
import time
import base64
import email
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional, Generator, Tuple

import google.oauth2.credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings

logger = logging.getLogger(__name__)

# Define the scopes required by Gmail API
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Rate limiting parameters
MAX_REQUESTS_PER_MINUTE = settings.RATE_LIMIT_REQUESTS
REQUEST_INTERVAL = 60.0 / MAX_REQUESTS_PER_MINUTE  # seconds between requests


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
        self._last_request_time = 0
    
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
    
    def _rate_limit_request(self):
        """
        Implement rate limiting to avoid hitting Gmail API limits.
        This ensures we wait a minimum amount of time between requests.
        """
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        
        if time_since_last_request < REQUEST_INTERVAL:
            sleep_time = REQUEST_INTERVAL - time_since_last_request
            logger.debug(f"Rate limiting: Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
            
        self._last_request_time = time.time()
    
    def get_email_list(self, query: str = '', max_results: int = 100, page_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a list of emails matching the query.
        
        Args:
            query: Gmail search query
            max_results: Maximum number of results per page
            page_token: Token for pagination
            
        Returns:
            Dictionary containing email metadata and next page token
        """
        if not self.service:
            self._build_service()
        
        try:
            self._rate_limit_request()
            
            request = {
                'userId': 'me',
                'q': query,
                'maxResults': min(max_results, settings.MAX_EMAILS_PER_BATCH)
            }
            
            if page_token:
                request['pageToken'] = page_token
                
            results = self.service.users().messages().list(**request).execute()
            
            return {
                'messages': results.get('messages', []),
                'next_page_token': results.get('nextPageToken')
            }
        except HttpError as error:
            logger.error(f"Error fetching emails: {error}")
            return {'messages': [], 'next_page_token': None}
    
    def get_email_batches(self, query: str = '', batch_size: int = 100) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Get batches of emails using pagination.
        
        Args:
            query: Gmail search query
            batch_size: Number of emails per batch
            
        Yields:
            Batches of email metadata
        """
        page_token = None
        
        while True:
            result = self.get_email_list(query, batch_size, page_token)
            messages = result.get('messages', [])
            
            if not messages:
                break
                
            yield messages
            
            page_token = result.get('next_page_token')
            if not page_token:
                break
                
            # Short pause between pagination requests
            time.sleep(0.5)
    
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
            self._rate_limit_request()
            
            message = self.service.users().messages().get(
                userId='me', 
                id=message_id,
                format='full'
            ).execute()
            
            return message
        except HttpError as error:
            logger.error(f"Error fetching email content: {error}")
            return {}
    
    def get_attachment(self, message_id: str, attachment_id: str) -> Optional[bytes]:
        """
        Get an email attachment.
        
        Args:
            message_id: The Gmail message ID
            attachment_id: The attachment ID
        
        Returns:
            The attachment data or None if not found
        """
        if not self.service:
            self._build_service()
            
        try:
            self._rate_limit_request()
            
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            if 'data' in attachment:
                # Convert from urlsafe base64 to standard base64
                data = attachment['data'].replace('-', '+').replace('_', '/')
                # Add padding if needed
                padding = 4 - (len(data) % 4)
                if padding:
                    data += '=' * padding
                
                return base64.b64decode(data)
            
            return None
        except HttpError as error:
            logger.error(f"Error fetching attachment: {error}")
            return None
    
    def parse_email_content(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Gmail API message format into a more usable structure.
        
        Args:
            message: The Gmail message object
            
        Returns:
            Dictionary with parsed email contents
        """
        if not message:
            return {}
            
        headers = {header['name'].lower(): header['value'] 
                  for header in message.get('payload', {}).get('headers', [])}
        
        # Extract basic email metadata
        email_data = {
            'id': message.get('id', ''),
            'thread_id': message.get('threadId', ''),
            'label_ids': message.get('labelIds', []),
            'snippet': message.get('snippet', ''),
            'subject': headers.get('subject', ''),
            'from': headers.get('from', ''),
            'to': headers.get('to', ''),
            'cc': headers.get('cc', ''),
            'bcc': headers.get('bcc', ''),
            'date': headers.get('date', ''),
            'content_type': '',
            'body_text': '',
            'body_html': '',
            'attachments': []
        }
        
        # Process parts to extract body and attachments
        payload = message.get('payload', {})
        if payload:
            parts = payload.get('parts', [])
            
            # If no parts, the payload itself might be the content
            if not parts and 'body' in payload:
                self._process_part(payload, email_data)
            else:
                for part in parts:
                    self._process_part(part, email_data)
        
        return email_data
    
    def _process_part(self, part: Dict[str, Any], email_data: Dict[str, Any], part_id: str = '') -> None:
        """
        Process a MIME part from the email.
        
        Args:
            part: The MIME part to process
            email_data: The email data dictionary to update
            part_id: ID path for nested parts
        """
        mime_type = part.get('mimeType', '')
        
        # For nested multipart messages
        if mime_type.startswith('multipart/'):
            nested_parts = part.get('parts', [])
            for i, nested_part in enumerate(nested_parts):
                new_part_id = f"{part_id}.{i+1}" if part_id else f"{i+1}"
                self._process_part(nested_part, email_data, new_part_id)
            return
        
        # Get part body
        body = part.get('body', {})
        
        # Handle attachments
        filename = part.get('filename', '')
        if filename and 'attachmentId' in body:
            email_data['attachments'].append({
                'id': body.get('attachmentId', ''),
                'filename': filename,
                'mime_type': mime_type,
                'size': body.get('size', 0),
                'part_id': part_id
            })
            return
            
        # Handle text content
        if 'data' in body:
            content = base64.urlsafe_b64decode(body['data']).decode('utf-8', errors='replace')
            
            if mime_type == 'text/plain':
                email_data['body_text'] = content
            elif mime_type == 'text/html':
                email_data['body_html'] = content
                
    def get_emails_with_labels(self, label_ids: List[str] = None, query: str = '', max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Get emails with specific labels or matching a query.
        
        Args:
            label_ids: List of label IDs to filter by
            query: Additional search query
            max_results: Maximum number of emails to return
            
        Returns:
            List of email data dictionaries
        """
        query_parts = []
        
        # Add label filters
        if label_ids:
            for label_id in label_ids:
                query_parts.append(f"label:{label_id}")
                
        # Add custom query if provided
        if query:
            query_parts.append(f"({query})")
            
        # Combine query parts
        final_query = " ".join(query_parts)
        
        emails = []
        count = 0
        
        # Get emails in batches
        for batch in self.get_email_batches(final_query, batch_size=settings.MAX_EMAILS_PER_BATCH):
            for message_meta in batch:
                if count >= max_results:
                    break
                    
                message_id = message_meta.get('id')
                message = self.get_email_content(message_id)
                
                if message:
                    email_data = self.parse_email_content(message)
                    emails.append(email_data)
                    count += 1
                    
            if count >= max_results:
                break
                
        return emails 