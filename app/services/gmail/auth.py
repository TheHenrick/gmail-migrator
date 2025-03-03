"""Gmail OAuth authentication flow."""

import secrets

from google_auth_oauthlib.flow import Flow
from requests_oauthlib import OAuth2Session

from app.config import settings


class OAuthFlow:
    """Handles OAuth flow for Gmail authentication."""

    def __init__(self) -> None:
        """
        Initialize the OAuth flow handler.

        Sets up the OAuth configuration with client credentials.
        """
        self.client_id = settings.GMAIL_CLIENT_ID
        self.client_secret = settings.GMAIL_CLIENT_SECRET
        self.redirect_uri = settings.GMAIL_REDIRECT_URI
        self.auth_base_url = "https://accounts.google.com/o/oauth2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.scope = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.labels",
        ]

    def get_authorization_url(self) -> tuple[str, str]:
        """
        Generate an authorization URL for the OAuth flow.

        Returns:
            A tuple with the authorization URL and state parameter
        """
        # Create a random state token for CSRF protection
        state = secrets.token_urlsafe(16)

        # Create an OAuth session
        oauth = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            state=state,
        )

        # Get the authorization URL
        authorization_url, _ = oauth.authorization_url(
            self.auth_base_url,
            access_type="offline",
            prompt="consent",
        )

        return authorization_url, state

    def exchange_code(self, code: str) -> dict[str, str]:
        """
        Exchange an authorization code for access and refresh tokens.

        Args:
            code: The authorization code received from the OAuth callback

        Returns:
            Dictionary containing the OAuth credentials
        """
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


# Create an instance for global access
oauth_flow = OAuthFlow()
