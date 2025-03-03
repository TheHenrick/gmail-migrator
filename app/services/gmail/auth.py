"""
Gmail OAuth authentication flow.
"""
import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials


class OAuthFlow:
    """
    Handles OAuth flow for Gmail authentication.
    """
    
    def __init__(self):
        """Initialize the OAuth flow."""
        self.client_id = os.environ.get('GMAIL_CLIENT_ID', 'your-client-id')
        self.client_secret = os.environ.get('GMAIL_CLIENT_SECRET', 'your-client-secret')
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.labels'
        ]
        self.redirect_uri = os.environ.get('GMAIL_REDIRECT_URI', 'http://localhost:5000/api/gmail/auth-callback')
        
    def get_authorization_url(self):
        """
        Get the authorization URL for Gmail OAuth.
        
        Returns:
            tuple: (auth_url, state) - The authorization URL and state
        """
        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                    'redirect_uris': [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        
        # Generate a state parameter to protect against CSRF
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return authorization_url, state
    
    def exchange_code(self, code):
        """
        Exchange an authorization code for access tokens.
        
        Args:
            code (str): The authorization code
            
        Returns:
            dict: The credentials dictionary
        """
        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                    'redirect_uris': [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        
        # Exchange authorization code for access token
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        # Convert credentials to a dictionary
        return {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }


# Create an instance for global access
oauth_flow = OAuthFlow() 