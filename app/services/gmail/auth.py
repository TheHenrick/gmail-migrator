"""Gmail OAuth authentication flow."""

from typing import NoReturn

from fastapi import HTTPException, status
from google_auth_oauthlib.flow import Flow

from app.config import settings


class OAuthFlow:
    """Handles OAuth flow for Gmail authentication."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        """
        Initialize the OAuth flow handler.

        Args:
            client_id: OAuth client ID (from UI or env)
            client_secret: OAuth client secret (from UI or env)
            redirect_uri: OAuth redirect URI (from UI or env)
        """
        self.client_id = client_id or settings.GMAIL_CLIENT_ID
        self.client_secret = client_secret or settings.GMAIL_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.GMAIL_REDIRECT_URI
        self.auth_base_url = "https://accounts.google.com/o/oauth2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.scope = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.labels",
        ]

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

            # Setup the OAuth flow
            flow = Flow.from_client_config(
                {
                    "installed": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uris": [self.redirect_uri],
                        "auth_uri": self.auth_base_url,
                        "token_uri": self.token_url,
                    }
                },
                scopes=self.scope,
                redirect_uri=self.redirect_uri,
            )

            # Generate the authorization URL
            auth_url, state = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
            )

            return auth_url, state
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating authorization URL: {e}",
            ) from e

    def exchange_code(self, code: str) -> dict[str, str]:
        """Exchange an authorization code for access and refresh tokens."""
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

            # Setup the OAuth flow
            flow = Flow.from_client_config(
                {
                    "installed": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uris": [self.redirect_uri],
                        "auth_uri": self.auth_base_url,
                        "token_uri": self.token_url,
                    }
                },
                scopes=self.scope,
                redirect_uri=self.redirect_uri,
            )

            # Exchange the authorization code for credentials
            flow.fetch_token(code=code)
            credentials = flow.credentials

            # Return the credentials as a dictionary
            return {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error exchanging code: {e}",
            ) from e


# Create a default instance using environment variables
oauth_flow = OAuthFlow()
