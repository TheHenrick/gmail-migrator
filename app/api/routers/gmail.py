"""Router for Gmail-related API endpoints."""

import logging
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.dependencies import get_gmail_client
from app.services.gmail.client import GmailClient

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/gmail", tags=["gmail"])


class EmailResponse(BaseModel):
    """Response model for email data."""

    id: str
    thread_id: str
    subject: str
    snippet: str
    from_address: str | None = None
    to_address: str | None = None
    date: str | None = None
    has_attachments: bool = False

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class OAuthCredentialsResponse(BaseModel):
    """Response model for OAuth credentials."""

    token: str
    refresh_token: str
    token_uri: str
    client_id: str
    client_secret: str
    scopes: list[str]


# Error types
EMAIL = "Email"
ATTACHMENT = "Attachment"


def raise_not_found(resource_type: str, resource_id: str) -> NoReturn:
    """
    Raise a 404 Not Found exception for a resource.

    Args:
        resource_type: Type of resource (email, attachment, etc.)
        resource_id: ID of the resource

    Raises:
        HTTPException: 404 Not Found exception
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource_type} with ID {resource_id} not found",
    )


def raise_server_error(message: str, error: Exception) -> NoReturn:
    """
    Raise a 500 Internal Server Error exception.

    Args:
        message: Error message
        error: Exception that caused the error

    Raises:
        HTTPException: 500 Internal Server Error exception
    """
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{message}: {str(error)}",
    ) from error


@router.post("/auth", response_model=OAuthCredentialsResponse)
async def authenticate_gmail() -> OAuthCredentialsResponse:
    """
    Authenticate with Gmail using OAuth2.

    Returns:
        OAuth credentials for Gmail API access
    """
    try:
        client = GmailClient()
        credentials = client.authenticate()

        return OAuthCredentialsResponse(
            token=credentials["token"],
            refresh_token=credentials["refresh_token"],
            token_uri=credentials["token_uri"],
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            scopes=credentials["scopes"],
        )
    except Exception as e:
        logger.exception("Error during Gmail authentication")
        raise_server_error("Authentication failed", e)


@router.get("/emails", response_model=list[EmailResponse])
async def list_emails(
    gmail_client: Annotated[GmailClient, Depends(get_gmail_client)],
    query: str = "",
    max_results: int = Query(100, gt=0, le=500),
    page_token: str | None = None,
) -> list[EmailResponse]:
    """
    List emails from Gmail that match the query.

    Args:
        gmail_client: Gmail client for API access
        query: Gmail search query
        max_results: Maximum number of results to return (1-500)
        page_token: Token for pagination

    Returns:
        List of email metadata
    """
    try:
        result = gmail_client.get_email_list(
            query=query, max_results=max_results, page_token=page_token
        )

        # Get full content for each message
        messages = []
        for message_meta in result.get("messages", []):
            try:
                message_id = message_meta.get("id")
                if not message_id:
                    continue

                email_data = gmail_client.get_email_content(message_id)

                # Convert to response model format
                messages.append(
                    EmailResponse(
                        id=email_data.get("id", ""),
                        thread_id=email_data.get("thread_id", ""),
                        subject=email_data.get("subject", ""),
                        snippet=email_data.get("snippet", ""),
                        from_address=email_data.get("from"),
                        to_address=email_data.get("to"),
                        date=email_data.get("date"),
                        has_attachments=bool(email_data.get("attachments")),
                    )
                )
            except Exception:
                logger.exception(f"Error processing message {message_meta.get('id')}")
                continue

        return messages
    except Exception as e:
        logger.exception("Error listing emails")
        raise_server_error("Failed to list emails", e)


@router.get("/emails/{email_id}", response_model=dict)
async def get_email(
    email_id: str, gmail_client: Annotated[GmailClient, Depends(get_gmail_client)]
) -> dict:
    """
    Get detailed content of a specific email.

    Args:
        email_id: Gmail message ID
        gmail_client: Gmail client for API access

    Returns:
        Full email content including body and metadata
    """
    try:
        email_data = gmail_client.get_email_content(email_id)

        if not email_data:
            raise_not_found(EMAIL, email_id)

        return email_data
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving email {email_id}")
        raise_server_error("Failed to retrieve email", e)


@router.get("/emails/{email_id}/attachments/{attachment_id}")
async def get_attachment(
    email_id: str,
    attachment_id: str,
    gmail_client: Annotated[GmailClient, Depends(get_gmail_client)],
) -> bytes:
    """
    Get a specific attachment from an email.

    Args:
        email_id: Gmail message ID
        attachment_id: Attachment ID
        gmail_client: Gmail client for API access

    Returns:
        Binary attachment data
    """
    try:
        attachment_data = gmail_client.get_attachment(email_id, attachment_id)

        if not attachment_data:
            raise_not_found(ATTACHMENT, attachment_id)

        # Returning binary response
        return attachment_data
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error retrieving attachment")
        raise_server_error("Failed to retrieve attachment", e)
