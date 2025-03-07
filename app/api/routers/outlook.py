"""Router for Outlook-related API endpoints."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_gmail_client, get_outlook_client
from app.services.gmail.client import GmailClient
from app.services.outlook.auth import OutlookAuthManager
from app.services.outlook.auth import oauth_flow as outlook_oauth_flow
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


class EmailSchema(BaseModel):
    """Schema for email representation."""

    id: str
    subject: str
    sender: str
    recipients: list[str]
    date: str
    has_attachments: bool


class EmailDetailSchema(EmailSchema):
    """Schema for detailed email representation."""

    body: str
    attachments: list[dict[str, Any]]


class OAuthCredentialsResponse(BaseModel):
    """Response model for OAuth credentials."""

    access_token: str
    refresh_token: str | None = None
    expires_in: int
    token_type: str
    scope: str


class OAuthConfig(BaseModel):
    """Model for OAuth client configuration."""

    client_id: str
    client_secret: str
    redirect_uri: str = "http://localhost:8000/outlook/auth-callback"


class AuthCodeRequest(BaseModel):
    """Request model for authorization code exchange."""

    code: str


@router.post("/auth-url", response_model=dict[str, str])
async def get_auth_url(
    config: OAuthConfig | None = None,
) -> dict[str, str]:
    """Get the OAuth authentication URL for Outlook."""
    try:
        logger.info("Generating Outlook OAuth URL")
        logger.info(f"Config provided: {config is not None}")

        # Get the OAuth flow instance
        flow_instance = outlook_oauth_flow
        if config:
            logger.info("Using custom OAuth config")
            flow_instance = OutlookAuthManager(
                client_id=config.client_id,
                client_secret=config.client_secret,
                redirect_uri=config.redirect_uri,
            )
        else:
            logger.info("Using default OAuth config")
            logger.info(f"Client ID: {settings.OUTLOOK_CLIENT_ID}")
            logger.info(f"Redirect URI: {settings.OUTLOOK_REDIRECT_URI}")

        # Get the authorization URL - use the correct method name
        auth_url = flow_instance.get_auth_url()
        logger.info(f"Generated Outlook OAuth URL: {auth_url}")

        return {"auth_url": auth_url}
    except Exception as e:
        logger.exception(f"Failed to get authentication URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get authentication URL: {str(e)}",
        ) from e


@router.get("/auth-callback")
async def auth_callback_get(
    code: str = Query(None, description="Authorization code"),
    error: str = Query(None, description="Error from OAuth provider"),
    config: OAuthConfig | None = None,
):
    """Handle the OAuth callback from Outlook with a GET request and redirect to the main page."""
    try:
        logger.info("Processing Outlook OAuth callback (GET)")

        if error:
            logger.error(f"OAuth error: {error}")
            # Redirect to main page with error parameter
            return RedirectResponse(url=f"/?error=outlook_auth_failed&message={error}")

        if not code:
            logger.error("No authorization code provided")
            # Redirect to main page with error parameter
            return RedirectResponse(url="/?error=outlook_auth_failed&message=no_code")

        logger.info(f"Received authorization code: {code[:10]}...")

        # Get the OAuth flow instance
        flow_instance = outlook_oauth_flow
        if config:
            flow_instance = OutlookAuthManager(
                client_id=config.client_id,
                client_secret=config.client_secret,
                redirect_uri=config.redirect_uri,
            )

        # Exchange the authorization code for credentials
        token_info = flow_instance.exchange_code(code)
        logger.info(f"Received token info: {token_info.keys()}")

        # Try to decode the access token to get user information
        import base64

        import jwt

        user_email = "Microsoft Account"  # Default value

        # Try to decode the JWT token
        try:
            # JWT tokens are in the format header.payload.signature
            # We only need the payload part
            token_parts = token_info["access_token"].split(".")
            if len(token_parts) >= 2:
                # Add padding if needed
                payload = token_parts[1]
                payload += "=" * ((4 - len(payload) % 4) % 4)

                # Decode the base64 payload
                decoded_payload = base64.b64decode(payload)
                token_data = jwt.decode(
                    decoded_payload, options={"verify_signature": False}
                )

                logger.info(f"Decoded token data: {token_data}")

                # Try to extract email from token
                if "email" in token_data:
                    user_email = token_data["email"]
                    logger.info(f"Found email in token: {user_email}")
                elif "upn" in token_data:
                    user_email = token_data["upn"]
                    logger.info(f"Found UPN in token: {user_email}")
                elif "unique_name" in token_data:
                    user_email = token_data["unique_name"]
                    logger.info(f"Found unique_name in token: {user_email}")
        except Exception as e:
            logger.warning(f"Could not decode token: {str(e)}")

        # Get user information from Microsoft Graph API
        try:
            # Create a client with the new token
            client = OutlookClient(token_info["access_token"])
            # Get user profile information
            user_info = client.get_user_profile()
            logger.info(f"User profile keys: {user_info.keys()}")

            # Try different fields that might contain the email
            if user_info.get("mail"):
                user_email = user_info["mail"]
                logger.info(f"Using mail field: {user_email}")
            elif user_info.get("userPrincipalName"):
                user_email = user_info["userPrincipalName"]
                logger.info(f"Using userPrincipalName field: {user_email}")
            elif user_info.get("otherMails") and len(user_info["otherMails"]) > 0:
                user_email = user_info["otherMails"][0]
                logger.info(f"Using otherMails field: {user_email}")
            else:
                logger.warning("No email field found in user profile")
                # Try to extract from any field that might look like an email
                for key, value in user_info.items():
                    if isinstance(value, str) and "@" in value:
                        user_email = value
                        logger.info(f"Found email-like value in {key}: {user_email}")
                        break

            logger.info(f"Final user email: {user_email}")
        except Exception as e:
            logger.exception(f"Could not get user profile: {str(e)}")

        # URL encode the email to avoid issues with special characters
        from urllib.parse import quote

        encoded_email = quote(user_email)
        logger.info(f"Encoded email: {encoded_email}")

        # Redirect to main page with success parameter
        # We'll handle storing the token in localStorage via JavaScript
        redirect_url = f"/?outlook_auth=success&token={token_info['access_token']}"

        if "refresh_token" in token_info and token_info["refresh_token"]:
            redirect_url += f"&refresh_token={token_info['refresh_token']}"

        redirect_url += f"&email={encoded_email}"

        logger.info(f"Redirecting to: {redirect_url}")
        return RedirectResponse(url=redirect_url)
    except Exception as e:
        logger.exception(f"Failed to exchange authorization code: {str(e)}")
        # Redirect to main page with error parameter
        return RedirectResponse(url=f"/?error=outlook_auth_failed&message={str(e)}")


@router.post("/auth-callback", response_model=OAuthCredentialsResponse)
async def auth_callback_post(
    request: AuthCodeRequest = None,
    code: str = Query(None, description="Authorization code"),
    config: OAuthConfig | None = None,
) -> OAuthCredentialsResponse:
    """Handle the OAuth callback from Outlook with a POST request."""
    try:
        logger.info("Processing Outlook OAuth callback (POST)")

        # Get the authorization code from either the request body or query parameter
        auth_code = request.code if request and request.code else code

        if not auth_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization code is required",
            )

        logger.info(f"Received authorization code: {auth_code[:10]}...")

        # Get the OAuth flow instance
        flow_instance = outlook_oauth_flow
        if config:
            flow_instance = OutlookAuthManager(
                client_id=config.client_id,
                client_secret=config.client_secret,
                redirect_uri=config.redirect_uri,
            )

        # Exchange the authorization code for credentials
        return flow_instance.exchange_code(auth_code)
    except Exception as e:
        logger.exception(f"Failed to exchange authorization code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange authorization code: {str(e)}",
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
