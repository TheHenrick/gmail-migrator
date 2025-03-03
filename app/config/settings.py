"""Application settings and configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# API Keys and Secrets
GMAIL_CLIENT_ID: str = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET: str = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REDIRECT_URI: str = os.getenv(
    "GMAIL_REDIRECT_URI", "http://localhost:8000/auth/callback"
)

# Outlook API credentials
OUTLOOK_CLIENT_ID: str = os.getenv("OUTLOOK_CLIENT_ID", "")
OUTLOOK_CLIENT_SECRET: str = os.getenv("OUTLOOK_CLIENT_SECRET", "")
OUTLOOK_REDIRECT_URI: str = os.getenv(
    "OUTLOOK_REDIRECT_URI", "http://localhost:8000/auth/outlook/callback"
)

# Yahoo API credentials
YAHOO_CLIENT_ID: str = os.getenv("YAHOO_CLIENT_ID", "")
YAHOO_CLIENT_SECRET: str = os.getenv("YAHOO_CLIENT_SECRET", "")
YAHOO_REDIRECT_URI: str = os.getenv(
    "YAHOO_REDIRECT_URI", "http://localhost:8000/auth/yahoo/callback"
)

# Application settings
DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
MAX_EMAILS_PER_BATCH: int = int(os.getenv("MAX_EMAILS_PER_BATCH", "100"))
# Requests per minute
RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
