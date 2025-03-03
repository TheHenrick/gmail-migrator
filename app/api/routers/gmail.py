"""
Gmail API router for Gmail authentication and email operations.
"""
import logging
from flask import Blueprint, request, jsonify, session

from app.services.gmail.client import GmailClient
from app.services.gmail.auth import oauth_flow

# Set up logging
logger = logging.getLogger(__name__)

# Create router
gmail_router = Blueprint('gmail', __name__)


def get_session_credentials():
    """Get credentials from session."""
    if 'credentials' not in session:
        return None
    return session['credentials']


@gmail_router.route('/auth-url', methods=['GET'])
def get_auth_url():
    """Get the Gmail OAuth authorization URL."""
    auth_url, state = oauth_flow.get_authorization_url()
    session['oauth_state'] = state
    return jsonify({"auth_url": auth_url})


@gmail_router.route('/auth-callback', methods=['GET'])
def auth_callback():
    """Handle the Gmail OAuth callback."""
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({"error": "Authorization code is missing"}), 400
    
    if 'oauth_state' not in session or session['oauth_state'] != state:
        return jsonify({"error": "Invalid state parameter"}), 400
    
    credentials = oauth_flow.exchange_code(code)
    session['credentials'] = credentials
    
    return jsonify({"message": "Authentication successful"})


@gmail_router.route('/emails', methods=['GET'])
def get_emails():
    """Get emails from Gmail."""
    credentials = get_session_credentials()
    if not credentials:
        return jsonify({"error": "Not authenticated"}), 401
    
    query = request.args.get('query', '')
    max_results = int(request.args.get('max_results', 10))
    page_token = request.args.get('page_token')
    
    client = GmailClient(credentials)
    emails = client.get_email_list(query=query, max_results=max_results, page_token=page_token)
    
    return jsonify(emails)


@gmail_router.route('/emails/<email_id>', methods=['GET'])
def get_email_detail(email_id):
    """Get email details from Gmail."""
    credentials = get_session_credentials()
    if not credentials:
        return jsonify({"error": "Not authenticated"}), 401
    
    client = GmailClient(credentials)
    email = client.get_email(email_id)
    
    return jsonify(email) 