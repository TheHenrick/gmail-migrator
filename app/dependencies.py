"""FastAPI dependencies for the application."""

import logging
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.services.gmail.client import GmailClient
from app.services.outlook.client import OutlookClient

logger = logging.getLogger(__name__)


async def get_gmail_client(
    authorization: Annotated[str | None, Header()] = None,
) -> GmailClient:
    """
    Dependency to get an authenticated Gmail client.

    Args:
        authorization: Authorization header with OAuth token

    Returns:
        Authenticated Gmail client

    Raises:
        HTTPException: If unauthorized or token is invalid
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token
    token = authorization.replace("Bearer ", "")

    # In a real app, you would validate the token and retrieve stored credentials
    # For now, we'll create a client with minimal validation
    try:
        # Here you would get the full credentials associated with this token
        # This is a simplified version
        credentials = {
            "token": token,
            # Other credential fields would be retrieved from storage
        }

        return GmailClient(credentials)
    except Exception as e:
        logger.exception("Error creating Gmail client")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_outlook_client(
    authorization: Annotated[str | None, Header()] = None,
) -> OutlookClient:
    """
    Dependency to get an authenticated Outlook client.

    Args:
        authorization: Authorization header with OAuth token

    Returns:
        Authenticated Outlook client

    Raises:
        HTTPException: If unauthorized or token is invalid
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token
    access_token = authorization.replace("Bearer ", "")

    try:
        return OutlookClient(access_token)
    except Exception as e:
        logger.exception("Error creating Outlook client")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Microsoft Graph API credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
