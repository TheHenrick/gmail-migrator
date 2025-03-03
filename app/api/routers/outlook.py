"""Router for Outlook-related API endpoints."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.dependencies import get_gmail_client, get_outlook_client
from app.services.gmail.client import GmailClient
from app.services.outlook.auth import oauth_flow
from app.services.outlook.client import OutlookClient

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/outlook", tags=["outlook"])


class FolderResponse(BaseModel):
    """Response model for folder data."""

    id: str
    display_name: str
    parent_folder_id: str | None = None
    child_folder_count: int = 0
    total_item_count: int = 0
    unread_item_count: int = 0

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class MessageResponse(BaseModel):
    """Response model for message data."""

    id: str
    subject: str
    body_preview: str
    from_address: str | None = None
    to_addresses: list[str] = []
    received_date: str | None = None
    has_attachments: bool = False

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class OAuthCredentialsResponse(BaseModel):
    """Response model for OAuth credentials."""

    access_token: str
    refresh_token: str | None = None
    expires_in: int
    token_type: str
    scope: str


@router.get("/auth-url", response_model=dict[str, str])
async def get_auth_url() -> dict[str, str]:
    """
    Get the OAuth authorization URL for Outlook.

    Returns:
        Dict[str, str]: Dictionary with authorization URL
    """
    auth_url = oauth_flow.get_auth_url()
    return {"auth_url": auth_url}


@router.get("/auth-callback", response_model=OAuthCredentialsResponse)
async def auth_callback(
    code: str = Query(..., description="Authorization code"),
) -> OAuthCredentialsResponse:
    """
    Handle OAuth2 callback from Microsoft.

    Args:
        code: Authorization code from OAuth2 flow

    Returns:
        OAuthCredentialsResponse: OAuth2 tokens and related information
    """
    try:
        result = oauth_flow.get_token_from_code(code)
        return OAuthCredentialsResponse(
            access_token=result.get("access_token", ""),
            refresh_token=result.get("refresh_token"),
            expires_in=result.get("expires_in", 0),
            token_type=result.get("token_type", "Bearer"),
            scope=result.get("scope", ""),
        )
    except Exception as e:
        logger.exception("Error in Outlook auth callback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}",
        ) from e


@router.get("/folders", response_model=list[FolderResponse])
async def list_folders(
    outlook_client: Annotated[OutlookClient, Depends(get_outlook_client)],
) -> list[FolderResponse]:
    """
    List all mail folders for the authenticated user.

    Args:
        outlook_client: Outlook client instance

    Returns:
        List[FolderResponse]: List of mail folders
    """
    try:
        folders_data = outlook_client.get_folders()
        folders = []

        for folder in folders_data:
            folders.append(
                FolderResponse(
                    id=folder.get("id", ""),
                    display_name=folder.get("displayName", ""),
                    parent_folder_id=folder.get("parentFolderId"),
                    child_folder_count=folder.get("childFolderCount", 0),
                    total_item_count=folder.get("totalItemCount", 0),
                    unread_item_count=folder.get("unreadItemCount", 0),
                )
            )

        return folders
    except Exception as e:
        logger.exception("Error listing Outlook folders")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing folders: {str(e)}",
        ) from e


@router.post("/folders", response_model=FolderResponse)
async def create_folder(
    name: str,
    outlook_client: Annotated[OutlookClient, Depends(get_outlook_client)],
    parent_folder_id: str | None = None,
) -> FolderResponse:
    """
    Create a new mail folder.

    Args:
        name: Name of the folder
        outlook_client: Outlook client instance
        parent_folder_id: ID of the parent folder (optional)

    Returns:
        FolderResponse: Created folder information
    """
    try:
        folder = outlook_client.create_folder(name, parent_folder_id)
        return FolderResponse(
            id=folder.get("id", ""),
            display_name=folder.get("displayName", ""),
            parent_folder_id=folder.get("parentFolderId"),
            child_folder_count=folder.get("childFolderCount", 0),
            total_item_count=folder.get("totalItemCount", 0),
            unread_item_count=folder.get("unreadItemCount", 0),
        )
    except Exception as e:
        logger.exception("Error creating Outlook folder")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating folder: {str(e)}",
        ) from e


@router.post("/migrate-email")
async def migrate_email(
    email_id: str,
    gmail_client: Annotated[GmailClient, Depends(get_gmail_client)],
    outlook_client: Annotated[OutlookClient, Depends(get_outlook_client)],
    folder_id: str | None = None,
) -> dict[str, str]:
    """
    Migrate a single email from Gmail to Outlook.

    Args:
        email_id: ID of the Gmail email to migrate
        gmail_client: Gmail client instance
        outlook_client: Outlook client instance
        folder_id: Target Outlook folder ID (optional)

    Returns:
        Dict[str, str]: Migration result
    """
    try:
        # Get the email from Gmail
        gmail_email = gmail_client.get_email(email_id)

        # Get any attachments
        attachments = []
        if gmail_email.get("has_attachments", False):
            for attachment in gmail_email.get("attachments", []):
                attachment_data = gmail_client.get_attachment(
                    email_id, attachment["id"]
                )
                attachments.append(
                    {
                        "name": attachment_data.get("filename", "attachment.dat"),
                        "content": attachment_data.get("data", b""),
                        "contentType": attachment_data.get("mime_type"),
                    }
                )

        # Migrate to Outlook
        migrated_email = outlook_client.migrate_email(
            gmail_message=gmail_email,
            attachments=attachments,
            folder_id=folder_id,
        )

        return {
            "status": "success",
            "gmail_id": email_id,
            "outlook_id": migrated_email.get("id", ""),
            "message": "Email migrated successfully",
        }

    except Exception as e:
        logger.exception(f"Error migrating email {email_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error migrating email: {str(e)}",
        ) from e


@router.post("/batch-migrate")
async def batch_migrate(
    email_ids: list[str],
    gmail_client: Annotated[GmailClient, Depends(get_gmail_client)],
    outlook_client: Annotated[OutlookClient, Depends(get_outlook_client)],
    folder_id: str | None = None,
) -> dict[str, Any]:
    """
    Migrate multiple emails from Gmail to Outlook.

    Args:
        email_ids: List of Gmail email IDs to migrate
        gmail_client: Gmail client instance
        outlook_client: Outlook client instance
        folder_id: Target Outlook folder ID (optional)

    Returns:
        Dict[str, Any]: Migration results
    """
    results = {
        "total": len(email_ids),
        "successful": 0,
        "failed": 0,
        "failed_ids": [],
    }

    for email_id in email_ids:
        try:
            # Get the email from Gmail
            gmail_email = gmail_client.get_email(email_id)

            # Get any attachments
            attachments = []
            if gmail_email.get("has_attachments", False):
                for attachment in gmail_email.get("attachments", []):
                    attachment_data = gmail_client.get_attachment(
                        email_id, attachment["id"]
                    )
                    attachments.append(
                        {
                            "name": attachment_data.get("filename", "attachment.dat"),
                            "content": attachment_data.get("data", b""),
                            "contentType": attachment_data.get("mime_type"),
                        }
                    )

            # Migrate to Outlook
            outlook_client.migrate_email(
                gmail_message=gmail_email,
                attachments=attachments,
                folder_id=folder_id,
            )

            results["successful"] += 1

        except Exception:
            logger.exception(f"Error migrating email {email_id}")
            results["failed"] += 1
            results["failed_ids"].append(email_id)

    return results
