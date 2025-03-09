"""Gmail API client for authentication and fetching emails."""

import base64
import logging
import os
import time
from collections.abc import Generator
from typing import Any

import google.oauth2.credentials
import google_auth_httplib2
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings

logger = logging.getLogger(__name__)

# Define the scopes required by Gmail API
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.metadata",
    "https://mail.google.com/",
]

# Error messages
NO_CREDENTIALS_ERROR = "No credentials available. Please authenticate first."

# Rate limiting parameters
MAX_REQUESTS_PER_MINUTE = settings.RATE_LIMIT_REQUESTS
REQUEST_INTERVAL = 60.0 / MAX_REQUESTS_PER_MINUTE  # seconds between requests


class GmailClient:
    """Client for interfacing with the Gmail API."""

    def __init__(
        self, credentials: dict[str, Any] | None = None, credentials_path: str = None
    ) -> None:
        """
        Initialize the Gmail client.

        Args:
            credentials: OAuth credentials for Gmail API access
            credentials_path: Path to credentials file
        """
        self.credentials = credentials
        self.credentials_path = credentials_path or "credentials.json"
        self.service = None
        self.request_count = 0
        self.requests_per_minute = settings.RATE_LIMIT_REQUESTS
        self._last_request_time = 0

        # Build the service if credentials are provided
        if self.credentials and "token" in self.credentials:
            try:
                self._build_service()
            except Exception:
                logger.exception("Failed to build Gmail service")
                # Don't raise here, let the service be None and handle it gracefully

    def authenticate(self) -> dict[str, Any]:
        """
        Authenticate with Gmail API using OAuth2.

        Returns:
            Dictionary containing OAuth credentials
        """
        try:
            # For testing, we might already have credentials
            if self.credentials:
                return self.credentials

            # Create a flow instance with client secrets
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path, GMAIL_SCOPES
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
        except Exception:
            logger.exception("Authentication error")
            raise

    def _build_service(self) -> None:
        """Build the Gmail API service."""
        if not self.credentials:
            error_msg = NO_CREDENTIALS_ERROR
            raise ValueError(error_msg)

        # For minimal credentials with just a token, use default values for other fields
        token = self.credentials.get("token")
        if not token:
            error_msg = "Token is required in credentials"
            raise ValueError(error_msg)

        # Use default values for missing fields
        refresh_token = self.credentials.get("refresh_token")
        token_uri = self.credentials.get(
            "token_uri", "https://oauth2.googleapis.com/token"
        )
        client_id = self.credentials.get("client_id", os.getenv("GMAIL_CLIENT_ID", ""))
        client_secret = self.credentials.get(
            "client_secret", os.getenv("GMAIL_CLIENT_SECRET", "")
        )
        scopes = self.credentials.get("scopes", GMAIL_SCOPES)

        # Check if we have all required fields for token refresh
        has_refresh_capability = all(
            [refresh_token, token_uri, client_id, client_secret]
        )

        # Log what we're using
        logger.info(
            f"Building Gmail service with token: {token[:10]}... and client_id: "
            f"{client_id[:10] if client_id else 'None'}"
        )
        logger.info(f"Refresh token available: {bool(refresh_token)}")
        logger.info(f"Has full refresh capability: {has_refresh_capability}")

        try:
            # If we don't have all required fields for refresh, we'll create
            # credentials that can't be refreshed. This is fine for short-lived
            # operations but will fail if the token expires
            if not has_refresh_capability:
                logger.warning(
                    "Missing required fields for token refresh. "
                    "Creating non-refreshable credentials."
                )
                logger.warning(
                    "The application will fail if the token expires. "
                    "Please re-authenticate."
                )

                # For API calls that don't require a refresh token
                from google.auth.transport.requests import Request
                from googleapiclient.http import build_http

                credentials = google.oauth2.credentials.Credentials(
                    token=token, scopes=scopes
                )

                # Create the service directly without refresh capability
                http = build_http()
                http = google_auth_httplib2.AuthorizedHttp(credentials, http=http)
                self.service = build("gmail", "v1", http=http)
                logger.info(
                    "Gmail service built successfully with non-refreshable credentials"
                )
            else:
                # Normal case with refresh token and all required fields
                logger.info("Creating fully refreshable credentials")
                credentials = google.oauth2.credentials.Credentials(
                    token=token,
                    refresh_token=refresh_token,
                    token_uri=token_uri,
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=scopes,
                )

                # Verify the token and refresh if needed
                if credentials.expired:
                    logger.info("Token is expired, refreshing...")
                    request = Request()
                    credentials.refresh(request)

                    # Update our stored credentials with the new token
                    self.credentials["token"] = credentials.token
                    logger.info("Token refreshed successfully")

                self.service = build("gmail", "v1", credentials=credentials)
                logger.info(
                    "Gmail service built successfully with refreshable credentials"
                )
        except Exception as e:
            logger.exception("Failed to build Gmail service")
            if "refresh" in str(e).lower():
                logger.exception(
                    "Token refresh failed. Please re-authenticate the application."
                )
            raise

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

            # Get the raw message for MIME content preservation
            raw_result = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="raw")
                .execute()
            )

            # Add raw content to the result
            result["raw"] = raw_result.get("raw", "")

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
            "body": {"plain": "", "html": ""},
            "attachments": [],
        }

        # Add raw content if available
        if "raw" in message:
            email_data["raw"] = message.get("raw", "")

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
                if "data" in payload["body"]:
                    body_data = payload["body"]["data"]
                    decoded_text = base64.urlsafe_b64decode(body_data).decode(
                        "utf-8", errors="replace"
                    )
                    email_data["body"]["plain"] = decoded_text
                elif "text/html" in mime_type and "data" in payload["body"]:
                    body_data = payload["body"]["data"]
                    decoded_html = base64.urlsafe_b64decode(body_data).decode(
                        "utf-8", errors="replace"
                    )
                    email_data["body"]["html"] = decoded_html

        return email_data

    def _process_part(self, part: dict[str, Any], email_data: dict[str, Any]) -> None:
        """
        Process a message part recursively.

        Args:
            part: The part to process
            email_data: The email data dictionary to update
        """
        # Handle nested parts
        if "parts" in part:
            for p in part["parts"]:
                self._process_part(p, email_data)
            return

        # Get mimetype and body
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})

        # Handle attachments
        if "attachmentId" in body:
            email_data["attachments"].append(
                {
                    "id": body["attachmentId"],
                    "filename": part.get("filename", ""),
                    "mimeType": mime_type,
                }
            )
        # Handle text bodies
        elif "data" in body:
            data = body["data"]

            # Convert from urlsafe base64 to standard base64
            data = data.replace("-", "+").replace("_", "/")

            # Add padding if needed
            missing_padding = len(data) % 4
            if missing_padding:
                data += "=" * (4 - missing_padding)

            decoded_data = base64.b64decode(data).decode("utf-8")

            if mime_type == "text/plain":
                email_data["body"]["plain"] = decoded_data
            elif mime_type == "text/html":
                email_data["body"]["html"] = decoded_data

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
