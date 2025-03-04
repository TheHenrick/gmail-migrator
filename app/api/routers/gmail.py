"""Router for Gmail-related API endpoints."""

import json
import logging
from typing import Annotated, Any, NoReturn

import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.dependencies import get_gmail_client, get_gmail_redirect_uri
from app.services.gmail.auth import OAuthFlow, exchange_code, oauth_flow
from app.services.gmail.client import GmailClient
from app.utils.exceptions import raise_server_error

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


class OAuthConfig(BaseModel):
    """Model for OAuth client configuration."""

    client_id: str
    client_secret: str
    redirect_uri: str = "http://localhost:8000/gmail/auth-callback"


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


# Models for Google Sign-In
class GoogleSignInRequest(BaseModel):
    """Request model for Google Sign-In authentication."""

    credential: str


# Add the new endpoint for Google Sign-In
@router.post("/google-signin", response_model=dict[str, Any])
async def google_signin(request: GoogleSignInRequest) -> dict[str, Any]:
    """Handle Google Sign-In and exchange for Gmail OAuth access."""
    try:
        # Get the OAuth flow instance
        flow_instance = oauth_flow

        # Exchange the Google credential for Gmail OAuth access
        # This will verify the token and request Gmail access
        return flow_instance.exchange_google_credential(request.credential)
    except HTTPException:
        raise
    except Exception as e:
        raise_server_error("Failed to process Google Sign-In", e)


# Auth-related endpoints
@router.get("/auth-url", response_model=dict[str, str])
@router.post("/auth-url", response_model=dict[str, str])
async def get_auth_url(
    config: OAuthConfig = None,
) -> dict[str, str]:
    """Get the OAuth authentication URL for Gmail."""
    try:
        logger.info("Generating Gmail OAuth URL")
        # Get the OAuth flow instance
        flow_instance = oauth_flow
        if config:
            flow_instance = OAuthFlow(
                client_id=config.client_id,
                client_secret=config.client_secret,
                redirect_uri=config.redirect_uri,
            )

        # Get the authorization URL
        auth_url, state = flow_instance.get_authorization_url()

        return {"auth_url": auth_url}
    except Exception as e:
        logger.exception("Error getting auth URL")
        raise_server_error("Failed to get authentication URL", e)


@router.get("/auth-callback", response_model=None)
@router.post("/auth-callback", response_model=None)
async def auth_callback(code: str) -> HTMLResponse:
    """Handle the OAuth callback from Gmail."""
    try:
        # Exchange the authorization code for tokens
        logger.info("Received authorization code, exchanging for token")
        token_response = await exchange_code(code, get_gmail_redirect_uri())

        # Get the access token for making API calls
        access_token = token_response.get("access_token", "")

        # Fetch user profile information from Google
        user_info = await fetch_user_profile(access_token)

        # Create HTML response that stores token and redirects
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <script>
                // Store the token in localStorage
                localStorage.setItem('gmailToken', '{access_token}');

                // Store actual user info from Google
                const userInfo = {user_info};

                // Store the user info
                localStorage.setItem('gmailUserInfo', JSON.stringify(userInfo));

                // Log the stored info
                console.log('Token stored:', localStorage.getItem('gmailToken'));
                console.log('User info stored:', localStorage.getItem('gmailUserInfo'));

                // Redirect to main page
                window.location.href = '/';
            </script>
        </head>
        <body>
            <h1>Authentication Successful</h1>
            <p>You have successfully authenticated with Gmail.
               Redirecting back to the application...</p>
        </body>
        </html>
        """

        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.exception("Error in auth callback")
        raise_server_error("Failed to process OAuth callback", e)


async def fetch_user_profile(access_token: str) -> str:
    """Fetch user profile information from Google using the access token."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code == 200:
                # Get user profile data and convert to JSON string for template
                profile_data = response.json()
                # Format as a JS object string
                return json.dumps(
                    {
                        "name": profile_data.get("name", "Gmail User"),
                        "email": profile_data.get("email", "gmail@user.com"),
                        "picture": profile_data.get("picture", ""),
                    }
                )

            # If not successful response
            error_msg = f"Failed to fetch user profile: {response.status_code}"
            logger.error(error_msg)
            return json.dumps(
                {"name": "Gmail User", "email": "gmail@user.com", "picture": ""}
            )
    except Exception as e:
        logger.exception("Error fetching user profile")
        raise_server_error("Failed to fetch user profile", e)
