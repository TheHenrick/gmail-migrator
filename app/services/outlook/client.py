"""Outlook client for Microsoft Graph API interactions."""

import base64
import logging
import mimetypes
from typing import Any

import requests
from fastapi import HTTPException

# Set up logging
logger = logging.getLogger(__name__)

# Microsoft Graph API base URL
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class OutlookClient:
    """Client for interacting with Microsoft Graph API for Outlook mail."""

    def __init__(self, access_token: str) -> None:
        """
        Initialize the Outlook client.

        Args:
            access_token: OAuth2 access token for Microsoft Graph API
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        request_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make a request to the Microsoft Graph API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            request_data: Request body and headers combined

        Returns:
            Dict[str, Any]: API response
        """
        url = f"{GRAPH_API_BASE}{endpoint}"

        # Extract headers from request_data if provided
        headers = self.headers.copy()
        data = None

        if request_data:
            if "headers" in request_data:
                headers.update(request_data.pop("headers"))
            data = request_data

        try:
            response = requests.request(method, url, params=params, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.RequestException as e:
            logger.exception(f"Error making request to {endpoint}")
            raise HTTPException(
                status_code=response.status_code if "response" in locals() else 500,
                detail=str(e),
            ) from e

    def get_mailbox_info(self) -> dict[str, Any]:
        """
        Get information about the user's mailbox.

        Returns:
            Dict[str, Any]: Mailbox information
        """
        return self._make_request("GET", "/me/mailfolders")

    def get_folders(self) -> list[dict[str, Any]]:
        """
        Get all mail folders from the user's mailbox.

        Returns:
            List[Dict[str, Any]]: List of mail folders
        """
        response = self._make_request("GET", "/me/mailfolders?$top=100&$expand=childFolders")
        return response.get("value", [])

    def create_folder(self, name: str, parent_folder_id: str | None = None) -> dict[str, Any]:
        """
        Create a new mail folder.

        Args:
            name: Name of the folder
            parent_folder_id: ID of the parent folder, if creating a subfolder

        Returns:
            Dict[str, Any]: Created folder information
        """
        data = {"displayName": name}

        endpoint = f"/me/mailfolders/{parent_folder_id}/childFolders" if parent_folder_id else "/me/mailfolders"

        return self._make_request("POST", endpoint, request_data=data)

    def get_messages(
        self,
        folder_id: str | None = None,
        query: str | None = None,
        top: int = 50,
        skip: int = 0,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get messages from a folder or search across all folders.

        Args:
            folder_id: ID of the folder to get messages from, or None for inbox
            query: Search query
            top: Maximum number of messages to return
            skip: Number of messages to skip

        Returns:
            Tuple with list of messages and next page token
        """
        params = {
            "$top": top,
            "$skip": skip,
            "$select": ("id,conversationId,subject,bodyPreview,receivedDateTime," "from,toRecipients,hasAttachments"),
            "$orderby": "receivedDateTime desc",
        }

        if query:
            params["$search"] = query

        endpoint = f"/me/mailfolders/{folder_id}/messages" if folder_id else "/me/messages"

        response = self._make_request("GET", endpoint, params=params)
        messages = response.get("value", [])
        next_link = response.get("@odata.nextLink")

        # Extract skip token from next_link if present
        skip_token = None
        if next_link and "$skiptoken=" in next_link:
            skip_token = next_link.split("$skiptoken=")[1].split("&")[0]

        return messages, skip_token

    def get_message(self, message_id: str) -> dict[str, Any]:
        """
        Get a specific message by ID.

        Args:
            message_id: ID of the message

        Returns:
            Dict[str, Any]: Message details
        """
        return self._make_request("GET", f"/me/messages/{message_id}?$expand=attachments")

    def get_attachment(self, message_id: str, attachment_id: str) -> dict[str, Any]:
        """
        Get a specific attachment.

        Args:
            message_id: ID of the message
            attachment_id: ID of the attachment

        Returns:
            Dict[str, Any]: Attachment data
        """
        return self._make_request("GET", f"/me/messages/{message_id}/attachments/{attachment_id}")

    def create_message(
        self,
        subject: str,
        body: str,
        to_recipients: list[str],
        **kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create a new message draft.

        Args:
            subject: Email subject
            body: Email body
            to_recipients: List of recipient email addresses
            **kwargs: Additional arguments including:
                folder_id: Target folder ID
                is_html: Whether body is HTML
                cc_recipients: List of CC recipient email addresses
                bcc_recipients: List of BCC recipient email addresses
                attachments: List of attachments

        Returns:
            Dict[str, Any]: Created message information
        """
        folder_id = kwargs.get("folder_id")
        is_html = kwargs.get("is_html", True)
        cc_recipients = kwargs.get("cc_recipients", [])
        bcc_recipients = kwargs.get("bcc_recipients", [])
        attachments = kwargs.get("attachments", [])

        # Format recipients
        to_list: list[dict[str, dict[str, str]]] = [{"emailAddress": {"address": email}} for email in to_recipients]
        cc_list: list[dict[str, dict[str, str]]] = [
            {"emailAddress": {"address": email}} for email in (cc_recipients or [])
        ]
        bcc_list: list[dict[str, dict[str, str]]] = [
            {"emailAddress": {"address": email}} for email in (bcc_recipients or [])
        ]

        # Create message data
        message_data: dict[str, Any] = {
            "subject": subject,
            "body": {
                "contentType": "html" if is_html else "text",
                "content": body,
            },
            "toRecipients": to_list,
        }

        if cc_list:
            message_data["ccRecipients"] = cc_list

        if bcc_list:
            message_data["bccRecipients"] = bcc_list

        # Create the draft message first
        endpoint = f"/me/mailfolders/{folder_id}/messages" if folder_id else "/me/messages"

        message = self._make_request("POST", endpoint, request_data=message_data)
        message_id = message.get("id")

        # Add attachments if any
        if attachments and message_id:
            for attachment in attachments:
                # Ensure content is bytes
                content = attachment["content"]
                if isinstance(content, str):
                    content = content.encode("utf-8")

                self.add_attachment(
                    message_id=message_id,
                    attachment_name=attachment["name"],
                    content_bytes=content,
                    content_type=attachment.get("contentType", "application/octet-stream"),
                )

        return message

    def add_attachment(
        self,
        message_id: str,
        attachment_name: str,
        content_bytes: bytes,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Add an attachment to a message.

        Args:
            message_id: ID of the message
            attachment_name: Name of the attachment
            content_bytes: Binary content
            content_type: MIME type of the attachment

        Returns:
            Dict[str, Any]: Attachment information
        """
        if content_type is None:
            content_type, _ = mimetypes.guess_type(attachment_name)
            if content_type is None:
                content_type = "application/octet-stream"

        attachment_data = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": attachment_name,
            "contentType": content_type,
            "contentBytes": base64.b64encode(content_bytes).decode("utf-8"),
        }

        return self._make_request(
            "POST",
            f"/me/messages/{message_id}/attachments",
            request_data=attachment_data,
        )

    def send_message(self, message_id: str) -> dict[str, Any]:
        """
        Send a previously created draft message.

        Args:
            message_id: ID of the draft message

        Returns:
            Dict[str, Any]: Response data
        """
        return self._make_request("POST", f"/me/messages/{message_id}/send")

    def import_email(
        self,
        mime_content: str,
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Import an email in MIME format to a folder.

        Args:
            mime_content: Email content in MIME format
            folder_id: Target folder ID

        Returns:
            Dict[str, Any]: Imported message information
        """
        # Upload as MIME content
        headers = {
            "Content-Type": "text/plain",
        }
        endpoint = f"/me/mailfolders/{folder_id}/messages/$value" if folder_id else "/me/messages/$value"

        request_data = {"headers": headers, "data": mime_content}

        return self._make_request("POST", endpoint, request_data=request_data)

    def migrate_email(
        self,
        gmail_message: dict[str, Any],
        attachments: list[dict[str, Any]],
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Migrate an email from Gmail to Outlook.

        Args:
            gmail_message: Gmail message data
            attachments: List of attachment data
            folder_id: Target folder ID in Outlook

        Returns:
            Dict[str, Any]: Migrated message information
        """
        # Extract recipient information
        to_address = gmail_message.get("to_address", "")
        to_recipients = [addr.strip() for addr in to_address.split(",")] if to_address else []

        # Extract subject and body
        subject = gmail_message.get("subject", "")
        body = gmail_message.get("body", "")
        is_html = "<html" in body.lower()

        # Create the message
        message = self.create_message(
            subject=subject,
            body=body,
            to_recipients=to_recipients,
            is_html=is_html,
            folder_id=folder_id,
        )

        # Add attachments
        message_id = message.get("id")
        if message_id and attachments:
            for attachment in attachments:
                self.add_attachment(
                    message_id=message_id,
                    attachment_name=attachment["name"],
                    content_bytes=attachment["content"],
                    content_type=attachment.get("contentType"),
                )

        return message
