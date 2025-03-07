"""Authentication manager for Outlook API."""

import logging
import os
from typing import Any

import msal
from fastapi import HTTPException, status

from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Define the token cache file path
TOKEN_CACHE_FILE = ".outlook_token_cache.json"

# Define the scopes for the Microsoft Graph API
SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/User.Read",
    "offline_access",
]


def _raise_token_error(result: dict[str, Any], operation: str) -> None:
    """
    Raise an HTTPException for token errors.

    Args:
        result: The result from the token operation
        operation: The operation being performed (acquire, refresh)

    Raises:
        HTTPException: With details about the token error
    """
    error = result.get("error", "unknown_error")
    error_description = result.get("error_description", "No description available")

    logger.error(f"Token {operation} error: {error} - {error_description}")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Token {operation} failed: {error} - {error_description}",
    )


class OutlookAuthManager:
    """Authentication manager for Outlook API."""

    def __init__(
        self,
        client_id: str = settings.OUTLOOK_CLIENT_ID,
        client_secret: str = settings.OUTLOOK_CLIENT_SECRET,
        redirect_uri: str = settings.OUTLOOK_REDIRECT_URI,
        authority: str = "https://login.microsoftonline.com/common",
        scopes: list[str] = None,
    ) -> None:
        """
        Initialize the Outlook authentication manager.

        Args:
            client_id: The client ID for the Outlook application
            client_secret: The client secret for the Outlook application
            redirect_uri: The redirect URI for the Outlook application
            authority: The authority URL for the Outlook application
            scopes: The scopes for the Outlook application
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.authority = authority
        self.scopes = scopes or SCOPES
        self.cache = self._load_cache()
        
        try:
            self.app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                client_secret=self.client_secret,
                authority=self.authority,
                token_cache=self.cache,
            )
            logger.info("MSAL ConfidentialClientApplication initialized successfully")
        except Exception:
            logger.exception("Error initializing MSAL application")
            raise

    def _load_cache(self) -> msal.SerializableTokenCache:
        """
        Load the token cache from file.

        Returns:
            SerializableTokenCache: The token cache
        """
        cache = msal.SerializableTokenCache()
        
        if os.path.exists(TOKEN_CACHE_FILE):
            try:
                with open(TOKEN_CACHE_FILE) as cache_file:
                    cache.deserialize(cache_file.read())
                logger.info(f"Loaded token cache from {TOKEN_CACHE_FILE}")
            except Exception:
                logger.exception(f"Failed to load token cache from {TOKEN_CACHE_FILE}")
        else:
            logger.info("Token cache file not found, creating new cache")
        
        return cache

    def _save_cache(self) -> None:
        """Save the token cache to file."""
        if self.cache.has_state_changed:
            try:
                with open(TOKEN_CACHE_FILE, "w") as cache_file:
                    cache_file.write(self.cache.serialize())
                logger.info(f"Saved token cache to {TOKEN_CACHE_FILE}")
            except Exception:
                logger.exception(f"Failed to save token cache to {TOKEN_CACHE_FILE}")

    def get_authorization_url(self) -> str:
        """
        Generate the authorization URL for OAuth flow.

        Returns:
            str: The authorization URL

        Raises:
            HTTPException: If authorization URL generation fails
        """
        try:
            auth_url = self.app.get_authorization_request_url(
                self.scopes,
                redirect_uri=self.redirect_uri,
                prompt="select_account",
            )
            
            logger.info(f"Generated authorization URL: {auth_url}")
            return auth_url
        except Exception as e:
            logger.exception("Error generating authorization URL")
            
            # If the error is related to reserved scopes, try with a mock URL for testing
            if "reserved" in str(e):
                logger.warning("Using mock URL due to scope error")
                return (
                    f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
                    f"?client_id={self.client_id}&response_type=code"
                    f"&redirect_uri={self.redirect_uri}"
                    f"&scope={'+'.join(self.scopes)}"
                )
                
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate authorization URL: {str(e)}",
            ) from e

    def get_token_from_code(self, code: str) -> dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: The authorization code from OAuth callback

        Returns:
            Dict[str, Any]: The token information

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
        except Exception:
            logger.exception("Error exchanging code for token")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to acquire token",
            ) from None

    def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh an access token using a refresh token.

        Args:
            refresh_token: The refresh token

        Returns:
            Dict[str, Any]: The new token information

        Raises:
            HTTPException: If token refresh fails
        """
        try:
            # First try to get token silently from cache
            accounts = self.app.get_accounts()
            if accounts:
                logger.info(f"Found {len(accounts)} accounts in cache")
                result = self.app.acquire_token_silent(self.scopes, account=accounts[0])
                if result:
                    logger.info("Got token silently from cache")
                    return result

            # If not in cache, use the refresh token
            logger.info("Getting token with refresh token")
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


# Create a global instance of the auth manager
oauth_flow = OutlookAuthManager()
