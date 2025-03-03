"""Utilities for parsing and formatting email content."""

import base64
import email
import re
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

# Constants
MIME_PART_TYPES = {
    "text/plain": "plain",
    "text/html": "html",
}
BASE64_PADDING_MOD = 4


def extract_email_address(email_string: str) -> tuple[str, str]:
    """
    Extract the name and email address from a formatted email string.

    Args:
        email_string: Email string in one of these formats:
            - "Name <email@example.com>"
            - "email@example.com"

    Returns:
        Tuple containing the name and email address
    """
    if not email_string:
        return "", ""

    # Check if the email has the format "Name <email@example.com>"
    match = re.match(r'"?([^"<]+)"?\s+<([^>]+)>', email_string)

    if match:
        name = match.group(1).strip()
        email_address = match.group(2).strip()
        return name, email_address

    # If no match, assume it's just an email address
    return "", email_string.strip()


def format_email_address(name: str, email_address: str) -> str:
    """
    Format a name and email address into a standard format.

    Args:
        name: Sender or recipient name
        email_address: Email address

    Returns:
        Formatted email address string
    """
    if name:
        return f'"{name}" <{email_address}>'
    return email_address


def parse_date(date_string: str) -> str:
    """
    Parse a date string into a standardized format.

    Args:
        date_string: Date string in RFC 2822 format

    Returns:
        ISO format date string
    """
    if not date_string:
        return ""

    try:
        # Parse the date from the email header format
        dt = email.utils.parsedate_to_datetime(date_string)
        return dt.isoformat()
    except (ValueError, TypeError):
        # If we can't parse it, return the original
        return date_string


def decode_body(part: dict[str, Any]) -> str:
    """
    Decode the body of an email part from base64.

    Args:
        part: Email part with base64 encoded data

    Returns:
        Decoded string or empty string if decoding fails
    """
    if not part or "body" not in part or "data" not in part["body"]:
        return ""

    try:
        data = part["body"]["data"]

        # Fix padding if needed
        padding = BASE64_PADDING_MOD - (len(data) % BASE64_PADDING_MOD)
        if padding < BASE64_PADDING_MOD:
            data += "=" * padding

        # Decode from base64url to bytes, then to string
        decoded_bytes = base64.urlsafe_b64decode(data)
        return decoded_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""


def create_mime_message(
    email_data: dict[str, Any], attachments: list[bytes] | None = None
) -> MIMEMultipart:
    """
    Create a MIME message from email data.

    Args:
        email_data: Dictionary containing email content and metadata
        attachments: List of attachment data

    Returns:
        Formatted MIME message
    """
    # Create the base message
    message = MIMEMultipart()

    # Add headers
    message["Subject"] = email_data.get("subject", "")

    if "from" in email_data:
        message["From"] = email_data["from"]

    if "to" in email_data:
        message["To"] = email_data["to"]

    if "cc" in email_data:
        message["Cc"] = email_data["cc"]

    # Add plain text body
    if "body" in email_data and "plain" in email_data["body"]:
        message.attach(MIMEText(email_data["body"]["plain"], "plain"))

    # Add HTML body
    if "body" in email_data and "html" in email_data["body"]:
        message.attach(MIMEText(email_data["body"]["html"], "html"))

    # Add attachments
    if attachments and "attachments" in email_data:
        for i, attachment_data in enumerate(attachments):
            if i < len(email_data["attachments"]):
                attachment_info = email_data["attachments"][i]

                attachment = MIMEApplication(attachment_data)
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=attachment_info.get("filename", f"attachment_{i}"),
                )

                message.attach(attachment)

    return message


def extract_recipients(email_data: dict[str, Any]) -> dict[str, list[str]]:
    """
    Extract all recipients from an email.

    Args:
        email_data: Dictionary containing email content and metadata

    Returns:
        Dictionary with to, cc, and bcc lists
    """
    recipients = {
        "to": [],
        "cc": [],
        "bcc": [],
    }

    # Extract To recipients
    if "to" in email_data and email_data["to"]:
        to_addresses = email_data["to"].split(",")
        recipients["to"] = [addr.strip() for addr in to_addresses]

    # Extract CC recipients
    if "cc" in email_data and email_data["cc"]:
        cc_addresses = email_data["cc"].split(",")
        recipients["cc"] = [addr.strip() for addr in cc_addresses]

    # Extract BCC recipients (if available)
    if "bcc" in email_data and email_data["bcc"]:
        bcc_addresses = email_data["bcc"].split(",")
        recipients["bcc"] = [addr.strip() for addr in bcc_addresses]

    return recipients
