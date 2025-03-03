"""
Email parsing utilities.
"""
import re
import base64
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Dict, Any, List, Optional, Tuple


def extract_email_address(email_string: str) -> Tuple[str, str]:
    """
    Extract name and email address from a formatted email string.
    
    Args:
        email_string: Email string in "Name <email@example.com>" or "email@example.com" format
        
    Returns:
        Tuple of (name, email)
    """
    # Extract email address with regex
    email_regex = r'[\w\.-]+@[\w\.-]+'
    email_match = re.search(email_regex, email_string)
    email_address = email_match.group(0) if email_match else ''
    
    # Extract name
    name_match = re.match(r'([^<]*)<', email_string)
    name = name_match.group(1).strip() if name_match else ''
    
    # If no name was found but email was, use part before @ as name
    if not name and email_address:
        name = email_address.split('@')[0]
        
    return name, email_address


def format_email_address(name: str, email_address: str) -> str:
    """
    Format name and email into a proper email string.
    
    Args:
        name: Person's name
        email_address: Email address
    
    Returns:
        Formatted email string (e.g., "Name <email@example.com>")
    """
    if name:
        return f"{name} <{email_address}>"
    return email_address


def parse_date(date_string: str) -> str:
    """
    Parse a date string into a standardized format.
    
    Args:
        date_string: Date string from email header
        
    Returns:
        Standardized date string
    """
    try:
        # Parse email date format
        parsed_date = email.utils.parsedate_to_datetime(date_string)
        # Format in ISO 8601 format
        return parsed_date.isoformat()
    except Exception:
        return date_string


def decode_body(part: Dict[str, Any]) -> str:
    """
    Decode email body content from base64.
    
    Args:
        part: Email body part with encoded data
        
    Returns:
        Decoded text
    """
    if 'body' in part and 'data' in part['body']:
        data = part['body']['data']
        # Fix padding if needed
        padding = 4 - (len(data) % 4)
        if padding != 4:
            data += '=' * padding
            
        # Convert from URL-safe base64 to standard base64
        data = data.replace('-', '+').replace('_', '/')
        
        try:
            return base64.b64decode(data).decode('utf-8', errors='replace')
        except Exception as e:
            return f"Error decoding: {str(e)}"
    
    return ""


def create_mime_message(email_data: Dict[str, Any], attachments: List[bytes] = None) -> MIMEMultipart:
    """
    Create a MIME message from parsed email data.
    
    Args:
        email_data: Parsed email data
        attachments: List of attachment data
        
    Returns:
        MIME message object
    """
    # Create message
    message = MIMEMultipart()
    
    # Set headers
    message['Subject'] = email_data.get('subject', '')
    message['From'] = email_data.get('from', '')
    message['To'] = email_data.get('to', '')
    
    if email_data.get('cc'):
        message['Cc'] = email_data.get('cc')
        
    if email_data.get('bcc'):
        message['Bcc'] = email_data.get('bcc')
    
    # Attach text parts
    if email_data.get('body_text'):
        part = MIMEText(email_data['body_text'], 'plain')
        message.attach(part)
    
    if email_data.get('body_html'):
        part = MIMEText(email_data['body_html'], 'html')
        message.attach(part)
    
    # Attach attachments if provided
    if attachments:
        for i, attachment_data in enumerate(attachments):
            if not attachment_data:
                continue
                
            attachment_info = email_data.get('attachments', [])[i] if i < len(email_data.get('attachments', [])) else {}
            filename = attachment_info.get('filename', f'attachment_{i}')
            
            attachment = MIMEApplication(attachment_data)
            attachment.add_header(
                'Content-Disposition', 
                f'attachment; filename="{filename}"'
            )
            message.attach(attachment)
    
    return message


def extract_recipients(email_data: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Extract all recipients from email data.
    
    Args:
        email_data: Parsed email data
        
    Returns:
        Dictionary with to, cc, and bcc recipient lists
    """
    recipients = {
        'to': [],
        'cc': [],
        'bcc': []
    }
    
    # Process 'To' field
    if 'to' in email_data and email_data['to']:
        to_list = email_data['to'].split(',')
        for addr in to_list:
            _, email_addr = extract_email_address(addr.strip())
            if email_addr:
                recipients['to'].append(email_addr)
    
    # Process 'Cc' field
    if 'cc' in email_data and email_data['cc']:
        cc_list = email_data['cc'].split(',')
        for addr in cc_list:
            _, email_addr = extract_email_address(addr.strip())
            if email_addr:
                recipients['cc'].append(email_addr)
    
    # Process 'Bcc' field
    if 'bcc' in email_data and email_data['bcc']:
        bcc_list = email_data['bcc'].split(',')
        for addr in bcc_list:
            _, email_addr = extract_email_address(addr.strip())
            if email_addr:
                recipients['bcc'].append(email_addr)
    
    return recipients 