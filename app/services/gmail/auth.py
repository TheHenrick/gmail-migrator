"""Gmail OAuth authentication flow."""

import logging
import os
import secrets
from typing import Any, NoReturn
from urllib.parse import urlencode

import requests
from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings


class OAuthFlow:
    """Gmail OAuth flow manager."""

    # Gmail API scopes
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.labels",
    ]

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        """
        Initialize the OAuth flow.

        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: OAuth redirect URI
        """
        self.client_id = client_id or settings.GMAIL_CLIENT_ID
        self.client_secret = client_secret or settings.GMAIL_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.GMAIL_REDIRECT_URI

    def get_authorization_url(self) -> tuple[str, str]:
        """Generate an OAuth2 authorization URL for Gmail."""
        try:
            # Helper function to raise HTTP exception
            def raise_config_error() -> NoReturn:
                raise HTTPException(  # noqa: TRY301
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing OAuth credentials. Please configure in settings.",
                )

            # Use provided credentials or fall back to environment variables
            if not all([self.client_id, self.client_secret, self.redirect_uri]):
                raise_config_error()

            # Instead of using InstalledAppFlow, let's construct the URL manually
            auth_base_url = "https://accounts.google.com/o/oauth2/v2/auth"

            # Generate a random state parameter for security
            state = secrets.token_urlsafe(16)

            # Prepare the parameters
            params = {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.SCOPES),
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "state": state,
            }

            # Construct the URL
            auth_url = f"{auth_base_url}?{urlencode(params)}"

            return auth_url, state
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating authorization URL: {e}",
            ) from e

    def exchange_code(self, code: str) -> dict[str, str]:
        """Exchange an authorization code for access and refresh tokens."""
        try:
            # Add logging for debugging
            logger = logging.getLogger(__name__)
            logger.debug(f"Starting exchange_code with client_id: {self.client_id}")
            logger.debug(f"Redirect URI: {self.redirect_uri}")

            # Helper function to raise HTTP exception
            def raise_config_error() -> NoReturn:
                raise HTTPException(  # noqa: TRY301
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing OAuth credentials. Please configure in settings.",
                )

            # Use provided credentials or fall back to environment variables
            if not all([self.client_id, self.client_secret, self.redirect_uri]):
                raise_config_error()

            # Exchange code for tokens
            logger.debug("Preparing to exchange code for tokens")
            token_url = "https://oauth2.googleapis.com/token"

            # Prepare the payload for token request
            token_payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }

            # Send the request to exchange code for tokens
            token_response = requests.post(token_url, data=token_payload, timeout=10)

            # Check if the token request was successful
            if token_response.status_code != 200:
                error_detail = (
                    token_response.json()
                    if token_response.content
                    else {"error": "Unknown error"}
                )
                logger.error(f"Token exchange failed: {error_detail}")
                raise HTTPException(  # noqa: TRY301
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error exchanging code: {error_detail}",
                )

            # Parse the token response
            token_data = token_response.json()
            logger.debug("Successfully exchanged code for tokens")

            # Format the response to match what the app expects
            return {
                "token": token_data.get("access_token", ""),
                "refresh_token": token_data.get("refresh_token", ""),
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scopes": self.SCOPES,
            }
        except Exception as e:
            logger.exception("Error in exchange_code")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error exchanging authorization code: {str(e)}",
            ) from e

    def exchange_google_credential(self, credential: str) -> dict[str, Any]:
        """
        Exchange a Google Sign-In credential for Gmail OAuth access.

        Args:
            credential: The ID token from Google Sign-In

        Returns:
            dict: OAuth credentials for Gmail API access
        """
        try:
            # Add debug logging
            logger = logging.getLogger(__name__)
            logger.debug(
                f"Starting exchange_google_credential with client_id: {self.client_id}"
            )

            # Verify the Google ID token
            logger.debug("Verifying Google ID token")
            idinfo = id_token.verify_oauth2_token(
                credential, google_requests.Request(), self.client_id
            )

            # Check if the token is valid
            logger.debug(f"Token issuer: {idinfo.get('iss')}")
            if idinfo["iss"] not in [
                "accounts.google.com",
                "https://accounts.google.com",
            ]:
                logger.error(f"Invalid token issuer: {idinfo['iss']}")

                def raise_invalid_issuer() -> NoReturn:
                    invalid_issuer = "Invalid token issuer"
                    raise ValueError(invalid_issuer)  # noqa: TRY301

                raise_invalid_issuer()

            # Get user info
            user_id = idinfo["sub"]
            email = idinfo.get("email")
            logger.debug(f"User ID: {user_id}, Email: {email}")

            # Since we can't directly exchange the ID token for Gmail API access,
            # we'll create a flow and generate an authorization URL
            logger.debug("Creating OAuth flow for Gmail API access")

            # Instead of using InstalledAppFlow, let's construct the URL manually
            auth_base_url = "https://accounts.google.com/o/oauth2/v2/auth"

            # Prepare the parameters
            params = {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.SCOPES),
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "login_hint": email,
            }

            # Construct the URL
            auth_url = f"{auth_base_url}?{urlencode(params)}"

            logger.debug(f"Generated authorization URL: {auth_url}")

            # Return a response with the authorization URL and user info
            return {
                "auth_url": auth_url,
                "user_id": user_id,
                "email": email,
                "requires_oauth_consent": True,
            }

        except ValueError as e:
            logger = logging.getLogger(__name__)
            logger.exception("ValueError in exchange_google_credential")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Google credential: {str(e)}",
            ) from e
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(
                f"Exception in exchange_google_credential: {str(e)}", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Google Sign-In: {str(e)}",
            ) from e


# Create a default instance using environment variables
oauth_flow = OAuthFlow()


async def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """
    Exchange an authorization code for access and refresh tokens.

    This is a standalone async version of the exchange_code method in OAuthFlow.

    Args:
        code: The authorization code to exchange
        redirect_uri: The redirect URI that was used in the authorization request

    Returns:
        dict: The token response data
    """
    logger = logging.getLogger(__name__)
    logger.debug("Starting async exchange_code")

    try:
        # Get credentials from environment
        client_id = os.getenv("GMAIL_CLIENT_ID")
        client_secret = os.getenv("GMAIL_CLIENT_SECRET")

        if not all([client_id, client_secret, redirect_uri]):
            logger.error("Missing OAuth configuration")

            def raise_missing_config() -> NoReturn:
                raise HTTPException(  # noqa: TRY301
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing OAuth credentials. Please check your configuration",
                )

            raise_missing_config()

        # Prepare the token request
        token_url = "https://oauth2.googleapis.com/token"
        token_payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        logger.debug(f"Exchanging code for tokens with redirect_uri: {redirect_uri}")

        # Use requests to exchange the code
        # (could be replaced with aiohttp for true async)
        token_response = requests.post(token_url, data=token_payload, timeout=10)

        if token_response.status_code != 200:
            error_detail = (
                token_response.json()
                if token_response.content
                else {"error": "Unknown error"}
            )
            logger.error(f"Token exchange failed: {error_detail}")

            def raise_token_error() -> NoReturn:
                raise HTTPException(  # noqa: TRY301
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error exchanging code: {error_detail}",
                )

            raise_token_error()

        # Parse the response
        token_data = token_response.json()
        logger.debug("Successfully exchanged code for tokens")

        # Return the token data
        return token_data

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception("Error in async exchange_code")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exchanging authorization code: {str(e)}",
        ) from e
