"""Outlook client for Microsoft Graph API interactions."""

import base64
import logging
import mimetypes
from typing import Any, Dict, List, Optional
import json

import httpx
from fastapi import HTTPException, status

# Set up logging
logger = logging.getLogger(__name__)

# Microsoft Graph API base URL
GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"


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
        logger.info("Initialized OutlookClient")

    def _make_request(
        self, method: str, endpoint: str, data: dict = None, params: dict = None
    ) -> dict:
        """
        Make a request to the Microsoft Graph API.

        Args:
            method: The HTTP method to use
            endpoint: The API endpoint to call
            data: The data to send in the request body
            params: The query parameters to include in the request

        Returns:
            dict: The response from the API

        Raises:
            HTTPException: If the request fails
        """
        url = f"{GRAPH_API_BASE_URL}{endpoint}"
        
        try:
            logger.info(f"Making {method} request to {url}")
            
            with httpx.Client(timeout=30.0) as client:
                if method.upper() == "GET":
                    response = client.get(url, headers=self.headers, params=params)
                elif method.upper() == "POST":
                    response = client.post(
                        url, headers=self.headers, json=data, params=params
                    )
                elif method.upper() == "PUT":
                    response = client.put(
                        url, headers=self.headers, json=data, params=params
                    )
                elif method.upper() == "DELETE":
                    response = client.delete(url, headers=self.headers, params=params)
                else:
                    error_msg = f"Unsupported HTTP method: {method}"
                    raise ValueError(error_msg)

            # Check if the request was successful
            response.raise_for_status()
            
            # Parse the response
            if response.content:
                return response.json()
            return {}
            
        except httpx.HTTPStatusError as e:
            logger.exception("HTTP error occurred")
            
            # Handle specific error codes
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed. Please sign in again.",
                ) from e
            
            if e.response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to access this resource.",
                ) from e
            
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The requested resource was not found.",
                ) from e
            
            # Try to parse the error response
            try:
                error_data = e.response.json()
                error_message = error_data.get("error", {}).get(
                    "message", "Unknown error"
                )
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"Microsoft Graph API error: {error_message}",
                ) from e
            except json.JSONDecodeError:
                # If we can't parse the error response, use the status code and text
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"Microsoft Graph API error: {e.response.text}",
                ) from e
                    
        except httpx.RequestError as e:
            logger.exception("Request error occurred")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error connecting to Microsoft Graph API: {str(e)}",
            ) from e
            
        except Exception as e:
            logger.exception("Unexpected error occurred")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}",
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
        response = self._make_request(
            "GET", "/me/mailfolders?$top=100&$expand=childFolders"
        )
        return response.get("value", [])

    def create_folder(
        self, name: str, parent_folder_id: str | None = None
    ) -> dict[str, Any]:
        """
        Create a new mail folder.

        Args:
            name: Name of the folder
            parent_folder_id: ID of the parent folder, if creating a subfolder

        Returns:
            Dict[str, Any]: Created folder information
        """
        data = {"displayName": name}

        if parent_folder_id:
            endpoint = f"/me/mailfolders/{parent_folder_id}/childFolders"
        else:
            endpoint = "/me/mailfolders"

        return self._make_request("POST", endpoint, data=data)

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
            "$select": (
                "id,conversationId,subject,bodyPreview,receivedDateTime,"
                "from,toRecipients,hasAttachments"
            ),
            "$orderby": "receivedDateTime desc",
        }

        if query:
            params["$search"] = query

        if folder_id:
            endpoint = f"/me/mailfolders/{folder_id}/messages"
        else:
            endpoint = "/me/messages"

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
        return self._make_request(
            "GET", f"/me/messages/{message_id}?$expand=attachments"
        )

    def get_attachment(self, message_id: str, attachment_id: str) -> dict[str, Any]:
        """
        Get a specific attachment.

        Args:
            message_id: ID of the message
            attachment_id: ID of the attachment

        Returns:
            Dict[str, Any]: Attachment data
        """
        return self._make_request(
            "GET", f"/me/messages/{message_id}/attachments/{attachment_id}"
        )

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
        to_list = [{"emailAddress": {"address": email}} for email in to_recipients]
        cc_list = [
            {"emailAddress": {"address": email}} for email in (cc_recipients or [])
        ]
        bcc_list = [
            {"emailAddress": {"address": email}} for email in (bcc_recipients or [])
        ]

        # Create message data
        message_data = {
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
        if folder_id:
            endpoint = f"/me/mailfolders/{folder_id}/messages"
        else:
            endpoint = "/me/messages"

        message = self._make_request("POST", endpoint, request_data=message_data)
        message_id = message.get("id")

        # Add attachments if any
        if attachments and message_id:
            for attachment in attachments:
                self.add_attachment(
                    message_id=message_id,
                    attachment_name=attachment["name"],
                    content_bytes=attachment["content"],
                    content_type=attachment.get("contentType"),
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
        endpoint = (
            f"/me/mailfolders/{folder_id}/messages/$value"
            if folder_id
            else "/me/messages/$value"
        )

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
        to_recipients = (
            [addr.strip() for addr in to_address.split(",")] if to_address else []
        )

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

    def get_user_profile(self) -> dict:
        """
        Get the user's profile information.

        Returns:
            dict: The user's profile information

        Raises:
            HTTPException: If the request fails
        """
        try:
            logger.info("Getting user profile")
            response = self._make_request(
                "GET", 
                "/me?$select=displayName,mail,userPrincipalName,id,otherMails"
            )
            
            # Log the fields that might contain email addresses
            email_fields = []
            if 'mail' in response:
                email_fields.append(f"mail: {response.get('mail')}")
            if 'userPrincipalName' in response:
                email_fields.append(
                    f"userPrincipalName: {response.get('userPrincipalName')}"
                )
            if 'otherMails' in response and response['otherMails']:
                email_fields.append(f"otherMails: {response.get('otherMails')}")
                
            if email_fields:
                logger.info(f"Found email fields: {', '.join(email_fields)}")
            else:
                logger.warning("No email fields found in user profile")
                
            return response
        except Exception:
            logger.exception("Error fetching user profile")

            # If full profile fails, try to get just the email
            try:
                logger.info("Trying to get just the email")
                email_response = self._make_request(
                    "GET", 
                    "/me?$select=mail,userPrincipalName,id,displayName"
                )
                logger.info(f"Email response: {email_response}")
                return email_response
            except Exception:
                logger.exception("Error fetching email")

                # If all else fails, return a minimal profile with default values
                return {
                    "id": "unknown",
                    "displayName": "Microsoft User",
                    "mail": None,
                    "userPrincipalName": None,
                }
