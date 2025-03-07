"""Outlook authentication module."""

import logging
from pathlib import Path
from typing import Any

import msal
from fastapi import HTTPException, status

from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Microsoft Graph API scopes
# These scopes allow reading and writing mail and accessing user profile
SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/User.Read",  # Add User.Read permission
]

# Cache file for MSAL token cache
CACHE_FILE = ".outlook_token_cache.json"
CACHE_PATH = Path(CACHE_FILE)


def _raise_token_error(result: dict[str, Any], operation: str) -> None:
    """
    Raise an HTTP exception for token errors.

    Args:
        result: Token operation result
        operation: Operation description (acquire/refresh)

    Raises:
        HTTPException: With appropriate error details
    """
    error_desc = result.get("error_description", "Unknown error")
    logger.error(f"Error {operation} token: {result}")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Failed to {operation} token: {error_desc}",
    )


class OutlookAuthManager:
    """Manager for Outlook/Microsoft Graph API OAuth2 authentication."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        """
        Initialize the Outlook authentication manager.

        Args:
            client_id: Microsoft app client ID
            client_secret: Microsoft app client secret
            redirect_uri: Redirect URI for OAuth2 flow
            scopes: OAuth2 scopes to request
        """
        self.client_id = client_id or settings.OUTLOOK_CLIENT_ID
        self.client_secret = client_secret or settings.OUTLOOK_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.OUTLOOK_REDIRECT_URI
        self.scopes = scopes or SCOPES

        logger.info(f"Initializing OutlookAuthManager with client_id: {self.client_id}")
        logger.info(f"Redirect URI: {self.redirect_uri}")
        logger.info(f"Scopes: {self.scopes}")

        try:
            self.app = msal.ConfidentialClientApplication(
                self.client_id,
                authority="https://login.microsoftonline.com/common",
                client_credential=self.client_secret,
                token_cache=self._load_cache(),
            )
            logger.info("MSAL ConfidentialClientApplication initialized successfully")
        except Exception as e:
            logger.exception(f"Error initializing MSAL application: {str(e)}")
            raise

    def _load_cache(self) -> msal.SerializableTokenCache:
        """
        Load token cache from file if it exists.

        Returns:
            msal.SerializableTokenCache: Token cache
        """
        cache = msal.SerializableTokenCache()
        if CACHE_PATH.exists():
            with CACHE_PATH.open() as cache_file:
                cache.deserialize(cache_file.read())
        return cache

    def _save_cache(self) -> None:
        """Save token cache to file."""
        if self.app.token_cache.has_state_changed:
            with CACHE_PATH.open("w") as cache_file:
                cache_file.write(self.app.token_cache.serialize())

    def get_auth_url(self) -> str:
        """
        Generate an authorization URL for the OAuth2 flow.

        Returns:
            str: Authorization URL
        """
        try:
            logger.info(f"Generating authorization URL with scopes: {self.scopes}")
            logger.info(f"Using redirect URI: {self.redirect_uri}")
            logger.info(f"Using client ID: {self.client_id}")

            # The MSAL library will automatically add the reserved scopes
            auth_url = self.app.get_authorization_request_url(
                self.scopes,
                redirect_uri=self.redirect_uri,
                prompt="select_account",
            )

            logger.info(f"Generated authorization URL: {auth_url}")
            return auth_url
        except Exception as e:
            logger.exception(f"Error generating authorization URL: {str(e)}")

            # If the error is related to reserved scopes, try with a mock URL for testing
            if "reserved" in str(e):
                logger.warning("Using mock URL due to scope error")
                mock_url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id={self.client_id}&response_type=code&redirect_uri={self.redirect_uri}&scope={'+'.join(self.scopes)}"
                return mock_url

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate authorization URL: {str(e)}",
            )

    def get_token_from_code(self, code: str) -> dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Dict[str, Any]: Token information

        Raises:
            HTTPException: If token acquisition fails
        """
        try:
            logger.info(f"Acquiring token with code: {code[:10]}...")
            logger.info(f"Using client ID: {self.client_id}")
            logger.info(f"Using client secret: {self.client_secret[:5]}...")
            logger.info(f"Using redirect URI: {self.redirect_uri}")
            logger.info(f"Using scopes: {self.scopes}")

            result = self.app.acquire_token_by_authorization_code(
                code, scopes=self.scopes, redirect_uri=self.redirect_uri
            )
            self._save_cache()

            if "error" in result:
                logger.error(f"Error in token response: {result}")
                _raise_token_error(result, "acquire")

            logger.info("Successfully acquired token")
            return result
        except Exception as e:
            logger.exception("Exception during token acquisition")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to acquire token: {str(e)}",
            ) from e

    def exchange_code(self, code: str) -> dict[str, Any]:
        """
        Exchange authorization code for access token and format the response.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Dict[str, Any]: Formatted token information

        Raises:
            HTTPException: If token acquisition fails
        """
        try:
            logger.info(f"Exchanging authorization code for token: {code[:10]}...")
            logger.info(f"Using client ID: {self.client_id}")
            logger.info(f"Using redirect URI: {self.redirect_uri}")

            token_info = self.get_token_from_code(code)

            # Format the response to match the expected structure
            return {
                "access_token": token_info.get("access_token", ""),
                "refresh_token": token_info.get("refresh_token"),
                "expires_in": token_info.get("expires_in", 3600),
                "token_type": token_info.get("token_type", "Bearer"),
                "scope": " ".join(token_info.get("scope", [])),
            }
        except Exception as e:
            logger.exception(f"Error exchanging code for token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to acquire token: {str(e)}",
            )

    def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh an access token using a refresh token.

        Args:
            refresh_token: Refresh token to use

        Returns:
            Dict[str, Any]: New token information

        Raises:
            HTTPException: If token refresh fails
        """
        try:
            result = self.app.acquire_token_by_refresh_token(
                refresh_token, scopes=self.scopes
            )
            self._save_cache()

            if "error" in result:
                _raise_token_error(result, "refresh")

            return result
        except Exception as e:
            logger.exception("Exception during token refresh")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to refresh token: {str(e)}",
            ) from e


# Create a singleton instance
oauth_flow = OutlookAuthManager()
