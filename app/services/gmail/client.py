"""Gmail API client for authentication and fetching emails."""

import base64
import logging
import time
from collections.abc import Generator
from typing import Any

import google.oauth2.credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings

logger = logging.getLogger(__name__)

# Define the scopes required by Gmail API
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
]

# Error messages
NO_CREDENTIALS_ERROR = "No credentials available. Please authenticate first."

# Rate limiting parameters
MAX_REQUESTS_PER_MINUTE = settings.RATE_LIMIT_REQUESTS
REQUEST_INTERVAL = 60.0 / MAX_REQUESTS_PER_MINUTE  # seconds between requests


class GmailClient:
    """Client for interfacing with the Gmail API."""

    def __init__(self, credentials: dict[str, Any] | None = None) -> None:
        """
        Initialize the Gmail client.

        Args:
            credentials: OAuth credentials for Gmail API access
        """
        self.credentials = credentials
        self.service = None
        self.request_count = 0
        self.requests_per_minute = settings.RATE_LIMIT_REQUESTS
        self._last_request_time = 0

    def authenticate(self) -> dict[str, Any]:
        """
        Authenticate with Gmail API using OAuth2.

        Returns:
            Dictionary containing OAuth credentials
        """
        # Create a flow instance with client secrets
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", GMAIL_SCOPES
        )

        # Run the OAuth flow
        credentials = flow.run_local_server(port=0)

        # Store credentials
        self.credentials = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }

        return self.credentials

    def _build_service(self) -> None:
        """Build the Gmail API service."""
        if not self.credentials:
            error_msg = NO_CREDENTIALS_ERROR
            raise ValueError(error_msg)

        credentials = google.oauth2.credentials.Credentials(
            token=self.credentials.get("token"),
            refresh_token=self.credentials.get("refresh_token"),
            token_uri=self.credentials.get("token_uri"),
            client_id=self.credentials.get("client_id"),
            client_secret=self.credentials.get("client_secret"),
            scopes=self.credentials.get("scopes"),
        )

        self.service = build("gmail", "v1", credentials=credentials)

    def _rate_limit_request(self) -> None:
        """
        Implement rate limiting to avoid hitting Gmail API limits.

        This ensures we wait a minimum amount of time between requests.
        """
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time

        # If less than the minimum interval has passed, wait
        min_interval = 60.0 / self.requests_per_minute
        if time_since_last_request < min_interval:
            time_to_wait = min_interval - time_since_last_request
            time.sleep(time_to_wait)

        # Update last request time
        self._last_request_time = time.time()

    def get_email_list(
        self, query: str = "", max_results: int = 100, page_token: str | None = None
    ) -> dict[str, Any]:
        """
        Get a list of emails matching the query.

        Args:
            query: Search query in Gmail format
            max_results: Maximum number of results to return
            page_token: Token for pagination

        Returns:
            Dictionary with email list and next page token
        """
        try:
            self._rate_limit_request()

            if not self.service:
                self._build_service()

            # Execute the Gmail API request
            result = (
                self.service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=max_results,
                    pageToken=page_token,
                )
                .execute()
            )

            # Extract messages and next page token
            messages = result.get("messages", [])
            next_page_token = result.get("nextPageToken")

            return {
                "messages": messages,
                "next_page_token": next_page_token,
            }
        except HttpError:
            logger.exception("Error fetching emails")
            return {"messages": [], "next_page_token": None}

    def get_email_batches(
        self, query: str = "", batch_size: int = 100
    ) -> Generator[list[dict[str, Any]], None, None]:
        """
        Get batches of emails using pagination.

        Args:
            query: Search query in Gmail format
            batch_size: Number of emails per batch

        Yields:
            Batches of email messages
        """
        page_token = None
        while True:
            result = self.get_email_list(
                query=query, max_results=batch_size, page_token=page_token
            )
            messages = result.get("messages", [])

            if not messages:
                break

            yield messages

            page_token = result.get("next_page_token")
            if not page_token:
                break

            # Add a small delay between requests
            time.sleep(0.5)

    def get_email_content(self, message_id: str) -> dict[str, Any]:
        """
        Get the full content of an email by its ID.

        Args:
            message_id: The Gmail message ID

        Returns:
            Parsed email content as a dictionary
        """
        try:
            self._rate_limit_request()

            if not self.service:
                self._build_service()

            # Get the full message
            result = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            return self.parse_email_content(result)
        except HttpError:
            logger.exception("Error fetching email content")
            return {}

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes | None:
        """
        Get an email attachment.

        Args:
            message_id: The Gmail message ID
            attachment_id: The attachment ID

        Returns:
            Attachment binary data or None if not found
        """
        try:
            self._rate_limit_request()

            if not self.service:
                self._build_service()

            # Get the attachment
            attachment = (
                self.service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )

            # Get the attachment data
            data = attachment.get("data")
            if data:
                return base64.urlsafe_b64decode(data)

            return None
        except HttpError:
            logger.exception("Error fetching attachment")
            return None

    def parse_email_content(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Parse Gmail API message format into a more usable structure.

        Args:
            message: The raw message from Gmail API

        Returns:
            Parsed email data as a dictionary
        """
        # Initialize email data
        email_data = {
            "id": message.get("id", ""),
            "thread_id": message.get("threadId", ""),
            "label_ids": message.get("labelIds", []),
            "snippet": message.get("snippet", ""),
            "body_text": "",
            "body_html": "",
            "attachments": [],
        }

        # Process headers
        if "payload" in message and "headers" in message["payload"]:
            headers = message["payload"]["headers"]
            for header in headers:
                header_name = header.get("name", "").lower()
                if header_name == "from":
                    email_data["from"] = header.get("value", "")
                elif header_name == "to":
                    email_data["to"] = header.get("value", "")
                elif header_name == "subject":
                    email_data["subject"] = header.get("value", "")
                elif header_name == "date":
                    email_data["date"] = header.get("value", "")
                elif header_name == "cc":
                    email_data["cc"] = header.get("value", "")
                elif header_name == "bcc":
                    email_data["bcc"] = header.get("value", "")

        # Process message body parts
        if "payload" in message:
            payload = message["payload"]
            if "parts" in payload:
                for part in payload["parts"]:
                    self._process_part(part, email_data)
            elif "body" in payload:
                # Handle single-part message
                mime_type = payload.get("mimeType", "")
                if "text/plain" in mime_type:
                    if "data" in payload["body"]:
                        body_data = payload["body"]["data"]
                        email_data["body_text"] = base64.urlsafe_b64decode(
                            body_data
                        ).decode("utf-8", errors="replace")
                elif "text/html" in mime_type and "data" in payload["body"]:
                    body_data = payload["body"]["data"]
                    email_data["body_html"] = base64.urlsafe_b64decode(
                        body_data
                    ).decode("utf-8", errors="replace")

        return email_data

    def _process_part(
        self, part: dict[str, Any], email_data: dict[str, Any], part_id: str = ""
    ) -> None:
        """
        Process a message part recursively.

        Args:
            part: Message part to process
            email_data: Email data dictionary to update
            part_id: Parent part ID for nested parts
        """
        current_part_id = part.get("partId", "")
        if part_id:
            current_part_id = f"{part_id}.{current_part_id}"

        mime_type = part.get("mimeType", "")

        # Handle nested parts
        if "parts" in part:
            for sub_part in part["parts"]:
                self._process_part(sub_part, email_data, current_part_id)

        # Handle attachment
        elif "attachment" in part.get("body", {}) and part.get("filename"):
            attachment_info = {
                "id": part.get("body", {}).get("attachmentId", ""),
                "filename": part.get("filename", ""),
                "mime_type": mime_type,
                "size": part.get("body", {}).get("size", 0),
                "part_id": current_part_id,
            }
            email_data["attachments"].append(attachment_info)

        # Handle text body
        elif "body" in part and "data" in part["body"]:
            body_data = part["body"]["data"]
            decoded_data = base64.urlsafe_b64decode(body_data).decode(
                "utf-8", errors="replace"
            )

            if "text/plain" in mime_type:
                email_data["body_text"] = decoded_data
            elif "text/html" in mime_type:
                email_data["body_html"] = decoded_data

    def get_emails_with_labels(
        self,
        label_ids: list[str] | None = None,
        query: str = "",
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get emails with specific labels or matching a query.

        Args:
            label_ids: List of label IDs to filter by
            query: Additional search query
            max_results: Maximum number of results

        Returns:
            List of email messages
        """
        # Build query string with labels if provided
        if label_ids:
            label_query = " ".join([f"label:{label_id}" for label_id in label_ids])
            query = f"{label_query} {query}" if query else label_query

        # Get emails matching the query
        result = self.get_email_list(query=query, max_results=max_results)
        messages = result.get("messages", [])

        # Fetch full content for each message
        full_messages = []
        for message in messages:
            message_id = message.get("id")
            if message_id:
                full_message = self.get_email_content(message_id)
                full_messages.append(full_message)

        return full_messages
