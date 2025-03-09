"""Outlook client for Microsoft Graph API interactions."""

import base64
import json
import logging
import mimetypes
from typing import Any

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

    def update_token(self, new_token: str) -> None:
        """
        Update the access token.

        Args:
            new_token: New OAuth2 access token
        """
        self.access_token = new_token
        self.headers = {
            "Authorization": f"Bearer {new_token}",
            "Content-Type": "application/json",
        }
        logger.info("Updated OutlookClient access token")

    async def validate_token(self) -> bool:
        """
        Validate the access token by making a simple request to the Microsoft Graph API.

        Returns:
            bool: True if the token is valid, False otherwise
        """
        try:
            # Make a simple request to get user info
            response = self._make_request("GET", "/me")
            logger.info(
                f"Token validation successful. User: "
                f"{response.get('displayName', 'Unknown')}"
            )
            return True
        except Exception as e:
            logger.exception("Token validation failed")
            if "401" in str(e) or "unauthorized" in str(e).lower():
                logger.exception(
                    "Access token appears to be expired or invalid. "
                    "Please re-authenticate."
                )
            return False

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict = None,
        params: dict = None,
        request_data: dict = None,
    ) -> dict:
        """
        Make a request to the Microsoft Graph API.

        Args:
            method: The HTTP method to use
            endpoint: The API endpoint to call
            data: The data to send in the request body
            params: The query parameters to include in the request
            request_data: Custom request data with headers and data

        Returns:
            dict: The response from the API

        Raises:
            HTTPException: If the request fails
        """
        url = f"{GRAPH_API_BASE_URL}{endpoint}"
        logger.info(f"Preparing {method} request to {url}")

        def raise_unsupported_method(method_name: str) -> None:
            """Raise ValueError for unsupported HTTP method."""
            error_msg = f"Unsupported HTTP method: {method_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        def handle_http_error(error: httpx.HTTPStatusError) -> None:
            """Handle HTTP errors and raise appropriate exceptions."""
            logger.exception(
                f"HTTP error occurred: {error.response.status_code} - "
                f"{error.response.reason_phrase}"
            )

            # Handle specific error codes
            if error.response.status_code == 401:
                logger.error("Authentication failed (401 Unauthorized)")
                logger.error(
                    "Your access token has expired. "
                    "Please re-authenticate the application."
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed. "
                    "Please sign in again to refresh your access token.",
                ) from error

            if error.response.status_code == 403:
                logger.error("Permission denied (403 Forbidden)")
                logger.error(
                    "Your account may not have the necessary permissions "
                    "for this operation."
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to access this resource. "
                    "Please check your account permissions.",
                ) from error

            if error.response.status_code == 404:
                logger.error("Resource not found (404 Not Found)")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The requested resource was not found.",
                ) from error

            # Try to parse the error response
            try:
                error_data = error.response.json()
                error_message = error_data.get("error", {}).get(
                    "message", "Unknown error"
                )
                logger.error(f"Microsoft Graph API error: {error_message}")

                # Check for token-related errors
                if "token" in error_message.lower() or "auth" in error_message.lower():
                    logger.error(
                        "This appears to be an authentication issue. "
                        "Please re-authenticate the application."
                    )

                raise HTTPException(
                    status_code=error.response.status_code,
                    detail=f"Microsoft Graph API error: {error_message}",
                ) from error
            except json.JSONDecodeError:
                # If we can't parse the error response, use the status code and text
                logger.exception(
                    f"Failed to parse error response: " f"{error.response.text[:80]}..."
                )
                raise HTTPException(
                    status_code=error.response.status_code,
                    detail=f"Microsoft Graph API error: {error.response.text}",
                ) from error

        try:
            logger.info(f"Making {method} request to {url}")
            if data:
                logger.info(f"Request data: {json.dumps(data)[:500]}...")
            if request_data:
                logger.info(
                    f"Custom request data headers: {request_data.get('headers', {})}"
                )
                logger.info(
                    f"Custom request data content length: "
                    f"{len(str(request_data.get('data', '')))}"
                )

            with httpx.Client(timeout=30.0) as client:
                if method.upper() == "GET":
                    logger.info("Executing GET request")
                    response = client.get(url, headers=self.headers, params=params)
                elif method.upper() == "POST":
                    if request_data:
                        # Handle custom request data with specific headers and data
                        logger.info("Executing POST request with custom request data")
                        custom_headers = {
                            **self.headers,
                            **request_data.get("headers", {}),
                        }
                        response = client.post(
                            url,
                            headers=custom_headers,
                            data=request_data.get("data"),
                            params=params,
                        )
                    else:
                        logger.info("Executing POST request with JSON data")
                        response = client.post(
                            url, headers=self.headers, json=data, params=params
                        )
                elif method.upper() == "PUT":
                    logger.info("Executing PUT request")
                    response = client.put(
                        url, headers=self.headers, json=data, params=params
                    )
                elif method.upper() == "DELETE":
                    logger.info("Executing DELETE request")
                    response = client.delete(url, headers=self.headers, params=params)
                else:
                    raise_unsupported_method(method)

            # Check if the request was successful
            logger.info(f"Response status code: {response.status_code}")
            response.raise_for_status()

            # Parse the response
            if response.content:
                try:
                    result = response.json()
                    logger.info(f"Received JSON response with {len(result)} keys")
                    return result
                except json.JSONDecodeError:
                    # If the response is not JSON, return the content as text
                    logger.info("Received non-JSON response")
                    return {"content": response.text}
            logger.info("Received empty response")
            return {}

        except httpx.HTTPStatusError as e:
            handle_http_error(e)

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
        try:
            logger.info("Starting to create message in Outlook")

            folder_id = kwargs.get("folder_id")
            logger.info(f"Target folder ID: {folder_id}")

            is_html = kwargs.get("is_html", True)
            logger.info(f"Is HTML content: {is_html}")

            cc_recipients = kwargs.get("cc_recipients", [])
            bcc_recipients = kwargs.get("bcc_recipients", [])
            attachments = kwargs.get("attachments", [])

            # Format recipients
            logger.info(f"Formatting {len(to_recipients)} recipients")
            to_list = [{"emailAddress": {"address": email}} for email in to_recipients]
            cc_list = [
                {"emailAddress": {"address": email}} for email in (cc_recipients or [])
            ]
            bcc_list = [
                {"emailAddress": {"address": email}} for email in (bcc_recipients or [])
            ]

            # Create message data
            logger.info("Creating message data structure")
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
                logger.info(f"Added {len(cc_list)} CC recipients")

            if bcc_list:
                message_data["bccRecipients"] = bcc_list
                logger.info(f"Added {len(bcc_list)} BCC recipients")

            # Create the draft message first
            if folder_id:
                endpoint = f"/me/mailfolders/{folder_id}/messages"
                logger.info(f"Using folder-specific endpoint: {endpoint}")
            else:
                endpoint = "/me/messages"
                logger.info("Using default messages endpoint")

            logger.info("Sending request to create message")
            message = self._make_request("POST", endpoint, data=message_data)

            if not message:
                logger.error("Received empty response when creating message")
                return {}

            message_id = message.get("id")
            logger.info(f"Message created with ID: {message_id}")

            # Add attachments if any
            if attachments and message_id:
                logger.info(f"Adding {len(attachments)} attachments")
                for i, attachment in enumerate(attachments):
                    logger.info(
                        f"Adding attachment {i+1}: {attachment.get('name', 'unnamed')}"
                    )
                    self.add_attachment(
                        message_id=message_id,
                        attachment_name=attachment["name"],
                        content_bytes=attachment["content"],
                        content_type=attachment.get("contentType"),
                    )
                    logger.info(f"Attachment {i+1} added successfully")

            logger.info("Message creation completed successfully")
            return message
        except Exception:
            logger.exception("Error creating message")
            return {}

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
        try:
            logger.info(f"Starting migration of email to Outlook folder: {folder_id}")

            # Extract recipient information
            to_address = gmail_message.get("to_address", "")
            logger.info(f"Extracted to_address: {to_address}")

            to_recipients = (
                [addr.strip() for addr in to_address.split(",")] if to_address else []
            )
            logger.info(f"Parsed to_recipients: {to_recipients}")

            # Extract subject and body
            subject = gmail_message.get("subject", "")
            logger.info(f"Extracted subject: {subject}")

            # Handle body which can be a string or a dictionary with 'plain'
            # and 'html' keys
            body = gmail_message.get("body", "")
            is_html = False

            if isinstance(body, dict):
                logger.info("Body is a dictionary with multiple formats")
                # Prefer HTML content if available
                if body.get("html"):
                    body_content = body.get("html", "")
                    is_html = True
                    logger.info("Using HTML body content")
                else:
                    body_content = body.get("plain", "")
                    logger.info("Using plain text body content")
            else:
                logger.info("Body is a string")
                body_content = body
                is_html = "<html" in body.lower()

            body_preview = (
                body_content[:100] + "..." if len(body_content) > 100 else body_content
            )
            logger.info(f"Extracted body (preview): {body_preview}")
            logger.info(f"Is HTML content: {is_html}")

            # Create the message
            logger.info("Creating message in Outlook")
            message = self.create_message(
                subject=subject,
                body=body_content,
                to_recipients=to_recipients,
                is_html=is_html,
                folder_id=folder_id,
            )

            if not message:
                logger.error("Failed to create message in Outlook")
                return {"error": "Failed to create message"}

            logger.info(f"Message created successfully with ID: {message.get('id')}")

            # Add attachments
            message_id = message.get("id")
            if message_id and attachments:
                logger.info(f"Adding {len(attachments)} attachments to message")
                for i, attachment in enumerate(attachments):
                    logger.info(
                        f"Adding attachment {i+1}/{len(attachments)}: "
                        f"{attachment.get('name', 'unnamed')}"
                    )
                    try:
                        self.add_attachment(
                            message_id=message_id,
                            attachment_name=attachment["name"],
                            content_bytes=attachment["content"],
                            content_type=attachment.get("contentType"),
                        )
                        logger.info(f"Successfully added attachment {i+1}")
                    except Exception:
                        logger.exception(f"Failed to add attachment {i+1}")

            logger.info("Email migration completed successfully")
            return message
        except Exception as e:
            logger.exception("Error during email migration")
            return {"error": str(e)}

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
                "GET", "/me?$select=displayName,mail,userPrincipalName,id,otherMails"
            )

            # Log the fields that might contain email addresses
            email_fields = []
            if "mail" in response:
                email_fields.append(f"mail: {response.get('mail')}")
            if "userPrincipalName" in response:
                email_fields.append(
                    f"userPrincipalName: {response.get('userPrincipalName')}"
                )
            if "otherMails" in response and response["otherMails"]:
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
                    "GET", "/me?$select=mail,userPrincipalName,id,displayName"
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
